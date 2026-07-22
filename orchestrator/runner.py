from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from orchestrator.logging_utils import Redactor


class Termination(StrEnum):
    COMPLETED = "completed"
    TERMINATED = "terminated"
    KILLED = "killed"
    SPAWN_FAILED = "spawn_failed"


@dataclass(frozen=True)
class ProcessEvidence:
    command: tuple[str, ...]
    cwd: str
    environment: Mapping[str, str]
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool
    termination: Termination
    timestamps: tuple[str, str]
    error: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Runner:
    def __init__(self, popen: Callable[..., Any] = subprocess.Popen,
                 clock: Callable[[], str] = _utc_now) -> None:
        self._popen = popen
        self._clock = clock

    def run(
        self,
        command: Sequence[str],
        cwd: Path,
        env: Mapping[str, str],
        timeout: float = 900,
        grace: float = 10,
        *,
        secret_values: Sequence[str] = (),
    ) -> ProcessEvidence:
        started = self._clock()
        redact = Redactor(secret_values)
        safe_command = redact.redact_values(command)
        safe_cwd = redact(str(cwd))
        safe_environment = MappingProxyType({key: redact(value) for key, value in env.items()})
        try:
            process = self._popen(
                tuple(command), cwd=cwd, env={**os.environ, **env}, shell=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except (OSError, ValueError) as exc:
            return ProcessEvidence(
                safe_command, safe_cwd, safe_environment, "", "", None, False,
                termination=Termination.SPAWN_FAILED, timestamps=(started, self._clock()),
                error=redact(str(exc)),)

        buffers: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
        read_errors: list[str] = []

        def drain(name: str) -> None:
            try:
                stream = getattr(process, name)
                while chunk := stream.read(65_536):
                    buffers[name].extend(chunk)
            except (OSError, ValueError) as exc:
                read_errors.append(f"{name}: {exc}")

        threads = [threading.Thread(target=drain, args=(name,)) for name in buffers]
        for thread in threads:
            thread.start()

        timed_out = False
        termination = Termination.COMPLETED
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                exit_code = process.wait(timeout=grace)
                termination = Termination.TERMINATED
            except subprocess.TimeoutExpired:
                process.kill()
                exit_code = process.wait()
                termination = Termination.KILLED
        for thread in threads:
            thread.join()

        def decode(value: bytearray) -> str:
            text = value.decode("utf-8", errors="replace").replace("\r\n", "\n")
            return redact(text)
        error = redact("; ".join(read_errors)) if read_errors else None
        return ProcessEvidence(
            safe_command, safe_cwd, safe_environment,
            decode(buffers["stdout"]), decode(buffers["stderr"]),
            exit_code=exit_code, timed_out=timed_out, termination=termination,
            timestamps=(started, self._clock()), error=error,
        )
