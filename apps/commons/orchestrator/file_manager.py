from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Mapping

from .models import FileEvidence


class PathContainmentError(ValueError):
    pass


class FileManager:
    SANDBOX_DIRECTORIES = (
        Path("input/diarios"),
        Path("output"),
        Path("logs"),
        Path("state"),
        Path("processed"),
    )

    def __init__(self, run_root: Path) -> None:
        self.root = run_root.resolve()

    def _contained(self, relative: Path) -> Path:
        if relative.is_absolute():
            raise PathContainmentError(f"absolute run path: {relative}")
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root):
            raise PathContainmentError(f"path escapes run: {relative}")
        return target

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _evidence(self, path: Path, role: str) -> FileEvidence:
        stat = path.stat()
        return FileEvidence(
            role=role,
            path=path.relative_to(self.root),
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            sha256=self._hash(path),
        )

    def create_sandbox(self) -> None:
        for relative in self.SANDBOX_DIRECTORIES:
            self._contained(relative).mkdir(parents=True, exist_ok=True)

    def copy_input(
        self, source: Path, destination: Path, role: str, extensions: set[str]
    ) -> FileEvidence:
        allowed = {extension.casefold() for extension in extensions}
        if source.suffix.casefold() not in allowed:
            raise ValueError(f"undeclared input extension: {source.suffix}")
        target = self._contained(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return self._evidence(target, role)

    def inventory(self, relative: Path, role: str) -> dict[Path, FileEvidence]:
        root = self._contained(relative)
        if not root.exists():
            return {}
        items = (
            self._evidence(self._contained(path.relative_to(self.root)), role)
            for path in sorted(root.rglob("*"))
            if path.is_file()
        )
        return {item.path: item for item in items}

    @staticmethod
    def new_files(
        before: Mapping[Path, FileEvidence], after: Mapping[Path, FileEvidence]
    ) -> tuple[FileEvidence, ...]:
        return tuple(
            after[path]
            for path in sorted(after)
            if path not in before or after[path] != before[path]
        )
