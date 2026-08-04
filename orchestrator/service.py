from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from adapters.naranjax.ma_chat import PostconditionError, ValidationError

from .file_manager import FileManager
from .logging_utils import Redactor, persist_logs
from .models import (ETLDefinition, FileEvidence, RunRequest, RunResult, RunStatus,
                     StateEffect, StateStatus)
from .run_store import LockHandle, RunBlockedError, RunStore
from .runner import ProcessEvidence, Termination
from .state_store import StatePromotionError


class RunService:
    def __init__(
        self,
        definition: ETLDefinition,
        adapter: Any,
        runner: Any,
        store: RunStore,
        state_store: Any,
        *,
        workspace: Path,
        now: Callable[[], str],
        file_manager: Callable[[Path], FileManager] = FileManager,
        log_persister: Callable[..., tuple[Path, ...]] = persist_logs,
    ) -> None:
        self.definition, self.adapter, self.runner = definition, adapter, runner
        self.store, self.state_store = store, state_store
        self.workspace, self.now = workspace.resolve(), now
        self.file_manager, self.log_persister = file_manager, log_persister

    def execute(self, request: RunRequest) -> RunResult:
        run = self.store.create_run(request.etl_id)
        manager, run_id = self.file_manager(run), run.name
        scope = f"{request.etl_id}/{request.business_date:%Y%m}"
        document: dict[str, Any] = {
            "run_id": run_id, "etl_id": request.etl_id,
            "business_date": request.business_date, "artifact_date": request.business_date,
            "lifecycle": [], "inputs": [], "process": None, "logs": [],
            "artifacts": [], "postconditions": {"outputs": "not_run", "state": "not_started"},
            "state": {"scope": scope, "status": StateStatus.NOT_STARTED},
            "blocker": None, "error": None,
        }
        self._transition(run, document, RunStatus.PREPARING)
        lock: LockHandle | None = None
        stateful = self.adapter.stateful
        try:
            self.adapter.validate(request)
            if stateful:
                self._state_preflight(request)
            lock = self.store.acquire_lock(
                request.etl_id, request.business_date.strftime("%Y%m"), run_id
            )
            document["inputs"] = self._stage_inputs(manager, request)
            if stateful:
                self._stage_current(run, request)
                document["state"]["status"] = StateStatus.STAGED
            before = manager.inventory(Path("output"), "output")
            command = self.adapter.command(self.definition, request, run)
            self._transition(run, document, RunStatus.RUNNING)
            process = self.runner.run(command, self.workspace / (self.definition.working_dir or Path()),
                                      self._environment(request), self.definition.timeout_seconds or 900,
                                      secret_values=tuple(request.environment.values()))
            self._record_process(run, document, process, request)
            if process.timed_out:
                return self._finish(run, document, RunStatus.TIMED_OUT, "timeout")
            if process.termination is Termination.SPAWN_FAILED:
                return self._finish(run, document, RunStatus.FAILED, "spawn_failed")
            if process.exit_code not in self.definition.allowed_exits:
                return self._finish(run, document, RunStatus.FAILED, "nonzero_exit")
            after = manager.inventory(Path("output"), "output")
            artifacts = self.adapter.outputs(self.definition, before, after)
            document["artifacts"] = artifacts
            document["postconditions"]["outputs"] = "passed"
            if stateful:
                staged = run / "state" / f"estado_{request.business_date:%Y%m}.csv"
                self.state_store.promote(
                    request.etl_id, request.business_date, staged, run_id,
                    require_change=self.adapter.requires_state_change,
                )
                document["state"]["status"] = StateStatus.PROMOTED
                document["postconditions"]["state"] = "promoted"
            else:
                document["postconditions"]["state"] = "not_applicable"
            return self._finish(run, document, RunStatus.SUCCEEDED, None)
        except ValidationError as error:
            return self._finish(run, document, RunStatus.BLOCKED, "validation_error", error)
        except RunBlockedError as error:
            return self._finish(run, document, RunStatus.BLOCKED, error.code, error)
        except PostconditionError as error:
            document["postconditions"]["outputs"] = "failed"
            return self._finish(run, document, RunStatus.FAILED, "postcondition_failed", error)
        except StatePromotionError as error:
            document["postconditions"]["state"] = "failed"
            if error.code == "recovery_required":
                document["state"]["status"] = StateStatus.RECOVERY_REQUIRED
                return self._finish(run, document, RunStatus.BLOCKED, error.code, error)
            return self._finish(run, document, RunStatus.FAILED, error.code, error)
        except (OSError, ValueError) as error:
            code = "promotion_failed" if document["postconditions"]["outputs"] == "passed" else "validation_error"
            return self._finish(run, document, RunStatus.FAILED, code, error)
        finally:
            if lock is not None:
                self.store.release_lock(lock)

    def _transition(self, run: Path, document: dict[str, Any], status: RunStatus) -> None:
        document["lifecycle"].append({"status": status, "at": self.now()})
        document["status"] = status
        self.store.write_metadata(run, document)

    def _finish(self, run: Path, document: dict[str, Any], status: RunStatus,
                code: str | None, error: Exception | None = None) -> RunResult:
        if code:
            detail = {"code": code, "message": code.replace("_", " ")}
            document["error"] = detail
            if status is RunStatus.BLOCKED:
                document["blocker"] = detail
        self._transition(run, document, status)
        state = StateStatus(document["state"]["status"])
        return RunResult(document["run_id"], status, code,
                         tuple(document["artifacts"]), StateEffect(document["state"]["scope"], state))

    def _state_preflight(self, request: RunRequest) -> None:
        lineage = Path(self.state_store.root) / request.etl_id / request.business_date.strftime("%Y%m")
        if (lineage / "recovery.json").exists() or (lineage / "recovery_required").exists():
            raise RunBlockedError("recovery_required", "state lineage requires recovery")
        if (lineage / f"estado_{request.business_date:%Y%m%d}.csv").exists():
            raise RunBlockedError("snapshot_exists", "state snapshot already exists")

    def _stage_inputs(self, manager: FileManager, request: RunRequest) -> tuple[FileEvidence, ...]:
        sources = {**dict(request.extras), "base": request.base,
                   "planes": request.planes, "pagos": request.pagos}
        fixed = {"planes": Path("input/diarios/planes.xlsx"),
                 "pagos": Path("input/diarios/pagos.csv")}
        evidence = []
        for spec in self.definition.inputs:
            source = sources.get(spec.role)
            if source is not None:
                destination = fixed.get(
                    spec.role, Path("input") / f"{spec.role}{source.suffix.casefold()}"
                )
                evidence.append(manager.copy_input(
                    source, destination, spec.role, set(spec.extensions)
                ))
        return tuple(evidence)

    def _stage_current(self, run: Path, request: RunRequest) -> None:
        current = (Path(self.state_store.root) / request.etl_id / request.business_date.strftime("%Y%m")
                   / f"estado_{request.business_date:%Y%m}.csv")
        if current.exists():
            shutil.copy2(current, run / "state" / current.name)

    def _environment(self, request: RunRequest) -> dict[str, str]:
        return {key: request.environment[key] for key in self.definition.environment_allowlist
                if key in request.environment}

    def _record_process(self, run: Path, document: dict[str, Any], process: ProcessEvidence,
                         request: RunRequest) -> None:
        legacy = tuple(path for path in (run / "logs").glob("*.log") if path.name not in {"stdout.log", "stderr.log"})
        secrets = request.environment.values()
        paths = (run, self.workspace, process.cwd, request.base, request.planes, request.pagos)
        logs = self.log_persister(run / "logs", process.stdout, process.stderr, legacy, secrets, paths)
        for path in legacy:
            path.unlink()
        document["logs"] = [(Path("logs") / path).as_posix() for path in logs]
        redactor = Redactor(secrets, paths)
        def clean(value: object) -> str:
            return redactor(str(value))
        document["process"] = {
            "command": [clean(value) for value in process.command],
            "cwd": clean(process.cwd),
            "environment": {key: clean(value) for key, value in process.environment.items()},
            "stdout": clean(process.stdout), "stderr": clean(process.stderr),
            "exit_code": process.exit_code, "timed_out": process.timed_out,
            "termination": process.termination, "timestamps": process.timestamps,
            "error": clean(process.error) if process.error else None,
        }
