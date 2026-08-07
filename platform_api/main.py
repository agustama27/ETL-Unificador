"""FastAPI layer for the ETL Unificador web console.

Wraps the existing orchestrator (catalog, service, stores) without touching
it. Named ``platform_api`` instead of the handoff's ``platform`` because a
top-level ``platform`` package would shadow the stdlib module of the same
name (pandas imports it).
"""

from __future__ import annotations

import io
import json
import os
import shutil
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from starlette.datastructures import UploadFile

from orchestrator.catalog import Catalog, CatalogError, adapter_for
from orchestrator.models import ETLDefinition, RunRequest
from orchestrator.run_store import RunStore
from orchestrator.runner import Runner
from orchestrator.service import RunService
from orchestrator.state_store import StateStore

from .catalog_meta import DEADLINE_HINTS, DEADLINES, INERT_REASONS, client_of
from .hardening import RunIndex, purge_expired, recover_orphans, webhook_notifier

LIVE_STATUSES = {"preparing", "running"}


class _ReservedRunStore:
    """Store proxy whose first create_run returns a pre-reserved run dir."""

    def __init__(self, store: RunStore, reserved: Path) -> None:
        self._store, self._reserved = store, reserved

    def create_run(self, etl_id: str) -> Path:
        if self._reserved is not None:
            reserved, self._reserved = self._reserved, None
            return reserved
        return self._store.create_run(etl_id)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)


def _default_service_factory(definition: ETLDefinition, adapter: Any,
                             store: Any, workspace: Path) -> RunService:
    return RunService(
        definition, adapter, Runner(), store,
        StateStore(workspace / "var/state"), workspace=workspace,
        now=lambda: datetime.now(timezone.utc).isoformat(),
    )


_WORKERS = ThreadPoolExecutor(
    max_workers=int(os.environ.get("ETL_MAX_CONCURRENT_RUNS", "2")),
    thread_name_prefix="etl-run")


def _default_executor(job: Callable[[], None]) -> None:
    """Non-daemon pool: pending runs finish before the interpreter exits."""
    _WORKERS.submit(job)


def _read_run(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "run.json").read_text("utf-8"))


def _run_summary(run_dir: Path, document: dict[str, Any]) -> dict[str, Any]:
    lifecycle = document.get("lifecycle") or []
    started = lifecycle[0]["at"] if lifecycle else None
    finished = lifecycle[-1]["at"] if document.get("status") not in LIVE_STATUSES and lifecycle else None
    return {
        "run_id": run_dir.name,
        "etl_id": document.get("etl_id"),
        "client": client_of(document.get("etl_id", "")),
        "business_date": document.get("business_date"),
        "status": document.get("status"),
        "error_code": (document.get("error") or {}).get("code"),
        "started_at": started,
        "finished_at": finished,
        "artifacts_count": len(document.get("artifacts") or []),
    }


def _run_detail(run_dir: Path, document: dict[str, Any]) -> dict[str, Any]:
    process = document.get("process") or {}
    stdout = (process.get("stdout") or "").splitlines()
    detail = _run_summary(run_dir, document)
    detail.update({
        "command": process.get("command") or [],
        "exit_code": process.get("exit_code"),
        "timed_out": process.get("timed_out"),
        "inputs": [
            {"role": item["role"], "name": Path(item["path"]).name,
             "size": item["size"], "sha256": item["sha256"]}
            for item in document.get("inputs") or []
        ],
        "artifacts": [
            {"role": item["role"], "name": Path(item["path"]).name,
             "size": item["size"], "path": item["path"]}
            for item in document.get("artifacts") or []
        ],
        "logs": {
            "stdout_tail": "\n".join(stdout[-40:]),
            "stderr": process.get("stderr") or "",
        },
        "postconditions": document.get("postconditions"),
        "state": document.get("state"),
    })
    return detail


def create_app(workspace: Path | None = None, *,
               adapters: dict[str, Any] | None = None,
               service_factory: Callable[..., Any] | None = None,
               executor: Callable[[Callable[[], None]], None] | None = None,
               today: Callable[[], date] = date.today,
               token: str | None = None,
               notifier: Callable[[dict[str, Any]], None] | None = None,
               retention_days: int | None = None) -> FastAPI:
    workspace = (workspace or Path(__file__).resolve().parents[1]).resolve()
    registered = adapters
    build_service = service_factory or _default_service_factory
    run_job = executor or _default_executor
    runs_root = workspace / "var/runs"
    state_root = workspace / "var/state"

    # Fail-closed: sin token configurado la API rechaza /api/*, salvo opt-out
    # explícito de desarrollo (ETL_AUTH_DISABLED=1) o token="" inyectado en tests.
    if token is not None:
        required_token, auth_unconfigured = token, False
    else:
        required_token = os.environ.get("ETL_CONSOLE_TOKEN", "")
        auth_unconfigured = (not required_token and os.environ.get(
            "ETL_AUTH_DISABLED", "").lower() not in ("1", "true"))
    if notifier is None:
        webhook = os.environ.get("ETL_NOTIFY_WEBHOOK", "")
        notifier = webhook_notifier(webhook) if webhook else None
    if retention_days is None:
        retention_days = int(os.environ.get("ETL_RETENTION_DAYS", "30"))

    recovery_store = RunStore(runs_root, state_root)
    orphaned = recover_orphans(
        runs_root, recovery_store.write_metadata,
        now=lambda: datetime.now(timezone.utc).isoformat())
    purge_expired((runs_root, workspace / "var/uploads"), retention_days)
    index = RunIndex(workspace / "var/index.sqlite", runs_root)
    index.refresh_full()

    app = FastAPI(title="ETL Unificador — Consola")

    @app.middleware("http")
    async def _authenticate(request: Request, call_next: Callable[..., Any]) -> Any:
        if request.url.path.startswith("/api"):
            if auth_unconfigured:
                return Response(
                    json.dumps({"detail": "Autenticación no configurada: seteá "
                                "ETL_CONSOLE_TOKEN o, sólo para desarrollo, "
                                "ETL_AUTH_DISABLED=1"}),
                    status_code=503, media_type="application/json")
            if required_token:
                supplied = request.headers.get("authorization", "")
                supplied = supplied.removeprefix("Bearer ").strip() or request.headers.get(
                    "x-api-token", "")
                if supplied != required_token:
                    return Response(
                        json.dumps({"detail": "Token inválido o ausente"}),
                        status_code=401, media_type="application/json")
        return await call_next(request)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"], allow_headers=["*"],
    )

    def catalog() -> Catalog:
        return Catalog.load_workspace(workspace, adapters=registered)

    def find_run(run_id: str) -> Path:
        if not runs_root.exists():
            raise HTTPException(404, "corrida no encontrada")
        for etl_dir in runs_root.iterdir():
            candidate = etl_dir / run_id
            if (candidate / "run.json").exists():
                return candidate
        raise HTTPException(404, "corrida no encontrada")

    @app.get("/api/catalog")
    def get_catalog() -> list[dict[str, Any]]:
        entries = []
        for item in catalog():
            try:
                adapter = adapter_for(item, registered) if item.adapter else None
            except CatalogError:
                adapter = None
            entries.append({
                "id": item.id,
                "name": item.name,
                "client": client_of(item.id),
                "readiness": item.readiness.value,
                "executable": item.executable,
                "reason": INERT_REASONS.get(item.id),
                "stateful": bool(getattr(adapter, "stateful", False)),
                "params": sorted(set(item.arguments)
                                 - {spec.role for spec in item.inputs}
                                 - {"business_date"}),
                "inputs": [
                    {"role": spec.role, "extensions": list(spec.extensions),
                     "required": spec.required}
                    for spec in item.inputs
                ],
                "outputs": [
                    {"role": spec.role, "glob": spec.glob,
                     "date_format": spec.date_format}
                    for spec in item.outputs
                ],
                "timeout_seconds": item.timeout_seconds,
                "deadline_hint": DEADLINE_HINTS.get(item.id),
            })
        return entries

    @app.post("/api/runs", status_code=202)
    async def post_run(request: Request,
                       etl_id: str = Form(...),
                       business_date: str = Form(...),
                       params: str = Form("{}")) -> dict[str, Any]:
        try:
            definition = catalog()[etl_id]
        except Exception as error:
            raise HTTPException(404, f"ETL desconocido: {etl_id}") from error
        if not definition.executable or definition.adapter is None:
            raise HTTPException(409, "El ETL no es ejecutable")
        try:
            parsed_date = date.fromisoformat(business_date)
        except ValueError as error:
            raise HTTPException(422, "Fecha inválida") from error
        # Deliberado (ADR-001, decisión 7): no existe reproceso de días caídos y los
        # legacy estampan la fecha del sistema en los nombres de salida.
        if parsed_date != today():
            raise HTTPException(
                422, "Solo se acepta la fecha de negocio de hoy")
        try:
            parsed_params = json.loads(params)
        except ValueError as error:
            raise HTTPException(422, "Parámetros inválidos") from error
        if not isinstance(parsed_params, dict) or not all(
            isinstance(name, str) and isinstance(value, (str, bool))
            for name, value in parsed_params.items()
        ):
            raise HTTPException(422, "Parámetros inválidos")

        form = await request.form()
        uploads: dict[str, UploadFile] = {
            role: value for role, value in form.items()
            if isinstance(value, UploadFile) and value.filename
        }
        declared = {spec.role: spec for spec in definition.inputs}
        for role in uploads:
            if role not in declared:
                raise HTTPException(422, f"El ETL no declara la entrada '{role}'")
        for role, spec in declared.items():
            upload = uploads.get(role)
            if upload is None:
                if spec.required:
                    raise HTTPException(422, f"Falta el archivo requerido: {role}")
                continue
            suffix = Path(upload.filename or "").suffix.casefold()
            allowed = {ext.casefold() for ext in spec.extensions}
            if suffix not in allowed:
                raise HTTPException(
                    422, f"Extensión inválida para {role}: se espera "
                         f"{', '.join(sorted(allowed))}")

        upload_dir = workspace / "var/uploads" / str(uuid4())
        upload_dir.mkdir(parents=True, exist_ok=True)
        staged: dict[str, Path] = {}
        for role, upload in uploads.items():
            suffix = Path(upload.filename or "").suffix.casefold()
            target = upload_dir / f"{role}{suffix}"
            with target.open("wb") as stream:
                shutil.copyfileobj(upload.file, stream)
            staged[role] = target

        store = RunStore(runs_root, state_root)
        reserved = store.create_run(etl_id)
        adapter = adapter_for(definition, registered)
        service = build_service(definition, adapter,
                                _ReservedRunStore(store, reserved), workspace)
        run_request = RunRequest(
            etl_id, parsed_date, inputs=staged, params=parsed_params,
        )

        def job() -> None:
            try:
                service.execute(run_request)
            finally:
                index.upsert(reserved)

        run_job(job)
        return {"run_id": reserved.name, "status": "preparing"}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run_dir = find_run(run_id)
        return _run_detail(run_dir, _read_run(run_dir))

    @app.get("/api/runs")
    def list_runs(client: str | None = None, etl_id: str | None = None,
                  status: str | None = None, business_date: str | None = None,
                  page: int = 1, page_size: int = 10) -> dict[str, Any]:
        items = [
            {**row, "client": client_of(row["etl_id"])}
            for row in index.query(etl_id=etl_id, status=status,
                                   business_date=business_date)
        ]
        if client:
            items = [item for item in items if item["client"] == client]
        total = len(items)
        pages = max(1, -(-total // page_size))
        start = (page - 1) * page_size
        return {"items": items[start:start + page_size], "total": total,
                "page": page, "pages": pages}

    @app.get("/api/schedule")
    def schedule() -> dict[str, Any]:
        current = today()
        entries = []
        for etl_id_, deadline in DEADLINES.items():
            if current.weekday() not in deadline["weekdays"]:
                continue
            entries.append({
                "etl_id": etl_id_,
                "client": client_of(etl_id_),
                "before": deadline["before"],
                "hint": DEADLINE_HINTS.get(etl_id_),
                "ran_today": index.ran_today(etl_id_, current.isoformat()),
            })
        return {"date": current.isoformat(), "orphaned_runs": orphaned,
                "deadlines": entries}

    @app.get("/api/runs/{run_id}/artifacts.zip")
    def download_all(run_id: str) -> Response:
        run_dir = find_run(run_id)
        document = _read_run(run_dir)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(run_dir / "run.json", "run.json")
            for item in document.get("artifacts") or []:
                source = run_dir / item["path"]
                archive.write(source, Path(item["path"]).name)
        headers = {"Content-Disposition":
                   f'attachment; filename="{run_id}_artefactos.zip"'}
        return Response(buffer.getvalue(), media_type="application/zip",
                        headers=headers)

    @app.get("/api/runs/{run_id}/artifacts/{role}")
    def download_artifact(run_id: str, role: str) -> FileResponse:
        run_dir = find_run(run_id)
        for item in _read_run(run_dir).get("artifacts") or []:
            if item["role"] == role:
                path = run_dir / item["path"]
                return FileResponse(path, filename=Path(item["path"]).name)
        raise HTTPException(404, f"artefacto no encontrado: {role}")

    @app.post("/api/runs/{run_id}/actions/{action}")
    def run_action(run_id: str, action: str) -> dict[str, Any]:
        run_dir = find_run(run_id)
        document = _read_run(run_dir)
        etl = document["etl_id"]
        if action == "notify_dev":
            payload = {
                "at": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id, "etl_id": etl,
                "error_code": (document.get("error") or {}).get("code"),
            }
            delivered = False
            if notifier is not None:
                try:
                    notifier(payload)
                    delivered = True
                except OSError as error:
                    payload["delivery_error"] = str(error)
            log = workspace / "var/notifications.jsonl"
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(payload) + "\n")
            return {"ok": True, "action": action, "delivered": delivered}
        if action == "free_lock":
            for etl_dir in runs_root.iterdir():
                for other in etl_dir.iterdir():
                    if not (other / "run.json").exists():
                        continue
                    live = _read_run(other)
                    if live.get("etl_id") == etl and live.get("status") in LIVE_STATUSES:
                        raise HTTPException(
                            409, "Hay una corrida activa de este ETL; no se puede liberar el lock")
            month = today().strftime("%Y%m")
            lock = state_root / etl / month / ".lock"
            if lock.exists():
                lock.rmdir()
                return {"ok": True, "action": action, "freed": True}
            return {"ok": True, "action": action, "freed": False}
        raise HTTPException(404, f"acción desconocida: {action}")

    return app


# Sin instancia a nivel de módulo: create_app() purga retención y recupera
# huérfanas al construirse, y eso no debe dispararse por un simple import.
# Levantar con: uvicorn "platform_api.main:create_app" --factory
