import ctypes
import json
import os
import shutil
from datetime import date
from pathlib import Path
from typing import Callable, NamedTuple
from uuid import uuid4

from .run_store import RunBlockedError


DirectoryApi = tuple[Callable[[Path], int], Callable[[int], None], Callable[[int], None]]


def _windows_directory_api() -> DirectoryApi:
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create, flush, close = kernel.CreateFileW, kernel.FlushFileBuffers, kernel.CloseHandle
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                       wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    flush.argtypes = close.argtypes = [wintypes.HANDLE]
    flush.restype = close.restype = wintypes.BOOL

    def open_directory(path: Path) -> int:
        handle = create(str(path), 0xC0000000, 7, None, 3, 0x02000000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        return int(handle)

    def checked(call: Callable[[int], int], handle: int) -> None:
        if not call(handle):
            raise ctypes.WinError(ctypes.get_last_error())

    return (open_directory, lambda handle: checked(flush, handle), lambda handle: checked(close, handle))


def _fsync_directory(path: Path, *, platform: str = os.name, api: DirectoryApi | None = None) -> None:
    if api is None:
        api = _windows_directory_api() if platform == "nt" else (
            lambda directory: os.open(
                directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)),
            os.fsync, os.close)
    open_directory, flush, close = api
    handle = open_directory(path)
    try:
        flush(handle)
    except BaseException:
        try:
            close(handle)
        except OSError:
            pass
        raise
    close(handle)


class StatePromotionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class Promotion(NamedTuple):
    snapshot: Path
    current: Path


class _PublishedError(OSError):
    pass


class StateStore:
    def __init__(
        self,
        state_root: Path,
        *,
        uuid_factory: Callable[[], object] = uuid4,
        replace: Callable[[Path, Path], None] = os.replace,
        file_fsync: Callable[[int], None] = os.fsync,
        directory_fsync: Callable[[Path], None] = _fsync_directory,
    ) -> None:
        self.root = state_root.resolve()
        self._uuid = lambda: str(uuid_factory())
        self._replace = replace
        self._fsync_file = file_fsync
        self._fsync_directory = directory_fsync

    def _lineage(self, etl_id: str, business_date: date) -> Path:
        lineage = (self.root / etl_id / business_date.strftime("%Y%m")).resolve()
        if not lineage.is_relative_to(self.root):
            raise ValueError(f"state path escapes root: {etl_id}")
        return lineage

    def _write_json(self, target: Path, payload: dict[str, object]) -> None:
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            self._fsync_file(stream.fileno())

    def _durable_json(self, target: Path, payload: dict[str, object]) -> None:
        temporary = target.with_name(f".{target.name}.{self._uuid()}.tmp")
        try:
            self._write_json(temporary, payload)
            self._replace(temporary, target)
            self._fsync_directory(target.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def _durable_copy(self, source: Path, target: Path) -> None:
        temporary = target.with_name(f".{target.name}.{self._uuid()}.tmp")
        published = False
        try:
            with source.open("rb") as incoming, temporary.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
                outgoing.flush()
                self._fsync_file(outgoing.fileno())
            self._replace(temporary, target)
            published = True
            self._fsync_directory(target.parent)
        except OSError as error:
            if published:
                raise _PublishedError(str(error)) from error
            raise
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _preflight(lineage: Path, snapshot: Path) -> None:
        if (lineage / "recovery.json").exists() or (lineage / "recovery_required").exists():
            raise RunBlockedError(
                "recovery_required", f"state lineage requires recovery: {lineage}"
            )
        if snapshot.exists():
            raise RunBlockedError(
                "snapshot_exists", f"state snapshot already exists: {snapshot}"
            )

    def _persist_recovery(self, lineage: Path, payload: dict[str, object], cause: OSError) -> None:
        try:
            self._durable_json(lineage / "recovery.json", payload)
        except OSError as primary_error:
            fallback_dir = lineage / "recovery_required"
            fallback = fallback_dir / f"{self._uuid()}.json"
            try:
                fallback_dir.mkdir(exist_ok=True)
                self._write_json(fallback, payload)
                self._fsync_directory(fallback_dir)
                self._fsync_directory(lineage)
            except OSError as fallback_error:
                raise StatePromotionError("recovery_evidence_failed",
                                          "state was partially promoted and durable recovery evidence failed") from fallback_error
            primary_error.add_note("primary recovery marker failed; fallback persisted")
        raise StatePromotionError("recovery_required",
                                  "snapshot was promoted but current state was not durably promoted; manual recovery required") from cause

    def promote(self, etl_id: str, business_date: date, staged_state: Path, run_id: str,
                *, require_change: bool = False) -> Promotion:
        lineage = self._lineage(etl_id, business_date)
        snapshot = lineage / f"estado_{business_date:%Y%m%d}.csv"
        current = lineage / f"estado_{business_date:%Y%m}.csv"
        recovery = {"schema": 1, "run_id": run_id,
                    "business_date": business_date.strftime("%Y%m%d"),
                    "snapshot": snapshot.name, "current": current.name}
        self._preflight(lineage, snapshot)
        if require_change and current.exists() and staged_state.read_bytes() == current.read_bytes():
            raise StatePromotionError("state_unchanged", "staged state is unchanged")
        lineage.mkdir(parents=True, exist_ok=True)
        try:
            self._durable_copy(staged_state, snapshot)
        except _PublishedError as error:
            self._persist_recovery(lineage, recovery, error)
        except OSError as error:
            raise StatePromotionError("promotion_failed",
                                      "state snapshot promotion failed before publication") from error
        try:
            self._durable_copy(staged_state, current)
        except OSError as error:
            self._persist_recovery(lineage, recovery, error)
        return Promotion(snapshot, current)
