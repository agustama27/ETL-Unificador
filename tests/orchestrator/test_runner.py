from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

from orchestrator.runner import Runner, Termination


JOB = Path(__file__).parents[1] / "support" / "fake_jobs.py"


def command(mode: str) -> tuple[str, ...]:
    return sys.executable, str(JOB), mode


def test_success_captures_both_streams_and_redacts_execution_context(tmp_path: Path) -> None:
    secret = "declared-secret"
    result = Runner().run(
        command("success") + (secret,), tmp_path, {"JOB_SECRET": secret}, secret_values=(secret,)
    )

    assert result.exit_code == 0
    assert result.termination is Termination.COMPLETED
    assert result.command[-1] == "[REDACTED]"
    assert result.environment == {"JOB_SECRET": "[REDACTED]"}
    assert f"out:{tmp_path}:" in result.stdout
    assert "err:[REDACTED]" in result.stderr
    assert secret not in repr(result)


def test_nonzero_exit_preserves_partial_stream_evidence(tmp_path: Path) -> None:
    result = Runner().run(command("nonzero"), tmp_path, {})

    assert (result.exit_code, result.timed_out, result.termination) == (
        7, False, Termination.COMPLETED
    )
    assert result.stdout == "partial-output\n"
    assert result.stderr == "failed-after-output\n"
    assert (tmp_path / "partial.csv").read_text(encoding="utf-8") == "partial"


def test_concurrent_drain_avoids_pipe_deadlock_and_redacts(tmp_path: Path) -> None:
    result = Runner().run(
        command("interleave"), tmp_path, {"JOB_SECRET": "PIPE_SECRET"},
        timeout=10, secret_values=("PIPE_SECRET",)
    )

    assert result.exit_code == 0
    assert result.stdout.count("stdout-") == 2_000
    assert result.stderr.count("stderr-") == 2_000
    assert "PIPE_SECRET" not in result.stdout + result.stderr


def test_timeout_terminates_and_preserves_partial_output(tmp_path: Path) -> None:
    result = Runner().run(command("sleep"), tmp_path, {}, timeout=0.5, grace=1)

    assert result.timed_out is True
    assert result.termination is Termination.TERMINATED
    assert result.stdout == "before-timeout\n"
    assert result.exit_code is not None


class StubbornProcess:
    def __init__(self) -> None:
        self.stdout = io.BytesIO(b"partial-out\n")
        self.stderr = io.BytesIO(b"partial-err\n")
        self.returncode: int | None = None
        self.waits = 0
        self.terminated = False
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        self.waits += 1
        if self.waits < 3:
            raise subprocess.TimeoutExpired("job", timeout or 0)
        self.returncode = 9
        return 9

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


def test_unresponsive_timeout_terminates_then_kills(tmp_path: Path) -> None:
    process = StubbornProcess()
    runner = Runner(popen=lambda *args, **kwargs: process)

    result = runner.run(("job",), tmp_path, {}, timeout=0.01, grace=0.01)

    assert process.terminated and process.killed
    assert result.termination is Termination.KILLED
    assert (result.stdout, result.stderr, result.exit_code) == (
        "partial-out\n", "partial-err\n", 9
    )


def test_spawn_failure_returns_typed_redacted_evidence(tmp_path: Path) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("cannot spawn SECRET")

    result = Runner(popen=fail).run(
        ("missing-SECRET",), tmp_path, {"TOKEN": "SECRET"}, secret_values=("SECRET",)
    )

    assert result.exit_code is None
    assert result.termination is Termination.SPAWN_FAILED
    assert result.error == "cannot spawn [REDACTED]"
    assert "SECRET" not in repr(result)
