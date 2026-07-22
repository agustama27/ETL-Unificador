from pathlib import Path

from orchestrator.logging_utils import Redactor, persist_logs


def test_redactor_replaces_declared_values_longest_first() -> None:
    redactor = Redactor(("token", "token-long", ""))

    assert redactor("token-long token") == "[REDACTED] [REDACTED]"
    assert redactor.redact_values(("--key=token-long",)) == ("--key=[REDACTED]",)


def test_persist_logs_is_deterministic_and_redacts_legacy_files(tmp_path: Path) -> None:
    legacy_b = tmp_path / "b.log"
    legacy_a = tmp_path / "a.log"
    legacy_b.write_text("second SECRET", encoding="utf-8")
    legacy_a.write_text("first SECRET", encoding="utf-8")
    log_dir = tmp_path / "evidence"

    first = persist_logs(log_dir, "out SECRET", "err SECRET", (legacy_b, legacy_a), ("SECRET",))
    second = persist_logs(log_dir, "out SECRET", "err SECRET", (legacy_a, legacy_b), ("SECRET",))

    assert first == second == (
        Path("stdout.log"), Path("stderr.log"), Path("legacy-a.log"), Path("legacy-b.log")
    )
    assert [path.name for path in sorted(log_dir.iterdir())] == [
        "legacy-a.log", "legacy-b.log", "stderr.log", "stdout.log"
    ]
    assert "SECRET" not in "".join(path.read_text(encoding="utf-8") for path in log_dir.iterdir())
    assert (log_dir / "legacy-a.log").read_text(encoding="utf-8") == "first [REDACTED]"
