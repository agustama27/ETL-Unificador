import json
import os
import socket
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, NamedTuple, cast
from uuid import uuid4

from .file_manager import FileManager


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class RunBlockedError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class LockHandle(NamedTuple):
    path: Path
    owner: Path


class RunStore:
    def __init__(
        self,
        runs_root: Path,
        state_root: Path,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        uuid_factory: Callable[[], object] = uuid4,
        replace: Callable[[Path, Path], None] = os.replace,
        directory_fsync: Callable[[Path], None] = _fsync_directory,
        remove_directory: Callable[[Path], None] = Path.rmdir,
    ) -> None:
        self.runs_root = runs_root.resolve()
        self.state_root = state_root.resolve()
        self._now = now
        self._uuid = lambda: str(uuid_factory())
        self._replace = replace
        self._fsync_directory = directory_fsync
        self._rmdir = remove_directory

    @staticmethod
    def _json_default(value: object) -> object:
        if is_dataclass(value):
            return asdict(cast(Any, value))
        if isinstance(value, Path):
            return value.as_posix()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        raise TypeError(f"unsupported metadata value: {type(value).__name__}")

    def _write_json(self, target: Path, payload: Mapping[str, object]) -> None:
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, default=self._json_default, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _durable_replace(self, target: Path, payload: Mapping[str, object]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{self._uuid()}.tmp")
        try:
            self._write_json(temporary, payload)
            self._replace(temporary, target)
            self._fsync_directory(target.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def create_run(self, etl_id: str) -> Path:
        timestamp = self._now().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        run = self.runs_root / etl_id / f"{timestamp}_{self._uuid()}"
        FileManager(run).create_sandbox()
        return run

    def write_metadata(self, run: Path, payload: Mapping[str, object]) -> None:
        self._durable_replace(run / "run.json", {"schema": 1, **payload})

    def acquire_lock(self, etl_id: str, month: str, run_id: str) -> LockHandle:
        path = self.state_root / etl_id / month / ".lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.mkdir()
        except FileExistsError as error:
            raise RunBlockedError("lock_exists", f"lock already exists: {path}") from error
        token = self._uuid()
        owner = path / token
        owner.mkdir()
        self._write_json(
            owner / "owner.json",
            {
                "schema": 1,
                "run_id": run_id,
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "acquired_at": self._now(),
                "token": token,
            },
        )
        self._fsync_directory(owner)
        self._fsync_directory(path)
        self._fsync_directory(path.parent)
        return LockHandle(path, owner)
    def release_lock(self, handle: LockHandle) -> bool:
        claimed = handle.path.with_name(f"{handle.path.name}.release-{self._uuid()}")
        try:
            for attempt in range(4):
                try:
                    self._replace(handle.path, claimed)
                    break
                except PermissionError:
                    if attempt == 3:
                        raise
            owner = claimed / handle.owner.name
            with (owner / "owner.json").open(encoding="utf-8") as stream:
                identity = json.load(stream)
            if not isinstance(identity, dict) or identity.get("token") != handle.owner.name:
                return False
            owner.joinpath("owner.json").unlink()
            self._rmdir(owner)
            self._rmdir(claimed)
            self._fsync_directory(handle.path.parent)
        except (OSError, ValueError):
            return False
        return True
