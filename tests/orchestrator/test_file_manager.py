import hashlib
from pathlib import Path

import pytest

from orchestrator.file_manager import FileManager, PathContainmentError


def test_sandbox_contains_required_directories(tmp_path: Path) -> None:
    run = tmp_path / "run"

    FileManager(run).create_sandbox()

    assert tuple(
        path.relative_to(run) for path in sorted(run.rglob("*")) if path.is_dir()
    ) == (
        Path("input"),
        Path("input/diarios"),
        Path("logs"),
        Path("output"),
        Path("processed"),
        Path("state"),
    )


@pytest.mark.parametrize(
    "destination", [Path("../escape.csv"), Path.cwd().resolve() / "escape.csv"]
)
def test_copy_rejects_escaping_and_absolute_destinations(
    tmp_path: Path, destination: Path
) -> None:
    source = tmp_path / "source.csv"
    source.write_bytes(b"safe")
    run = tmp_path / "run"

    with pytest.raises(PathContainmentError):
        FileManager(run).copy_input(source, destination, "base", {".csv"})

    assert not run.exists()
    assert not (tmp_path / "escape.csv").exists()


def test_copy_checks_extension_before_mutation(tmp_path: Path) -> None:
    source = tmp_path / "source.exe"
    source.write_bytes(b"unsafe")
    run = tmp_path / "run"

    with pytest.raises(ValueError, match="extension"):
        FileManager(run).copy_input(source, Path("input/source.exe"), "base", {".csv"})

    assert not run.exists()


def test_copy_is_contained_and_hash_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "outside" / "source.CSV"
    source.parent.mkdir()
    source.write_bytes(b"account,amount\n1,25\n")
    run = tmp_path / "run"
    manager = FileManager(run)

    first = manager.copy_input(source, Path("input/first.csv"), "base", {".csv"})
    second = manager.copy_input(source, Path("input/second.csv"), "base", {".CSV"})

    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    assert (first.path, second.path) == (
        Path("input/first.csv"), Path("input/second.csv")
    )
    assert (first.sha256, second.sha256) == (expected, expected)
    assert (run / first.path).read_bytes() == source.read_bytes()


def test_output_diff_reports_new_or_changed_files_in_order(tmp_path: Path) -> None:
    manager = FileManager(tmp_path / "run")
    manager.create_sandbox()
    output = manager.root / "output"
    existing = output / "existing.csv"
    existing.write_text("before", encoding="utf-8")
    (output / "unchanged.csv").write_text("same", encoding="utf-8")
    before = manager.inventory(Path("output"), "artifact")

    existing.write_text("changed", encoding="utf-8")
    (output / "z.csv").write_text("last", encoding="utf-8")
    (output / "a.csv").write_text("first", encoding="utf-8")
    after = manager.inventory(Path("output"), "artifact")

    changed_files = manager.new_files(before, after)
    assert tuple(item.path for item in changed_files) == (
        Path("output/a.csv"), Path("output/existing.csv"), Path("output/z.csv")
    )
    assert changed_files[1].sha256 == hashlib.sha256(b"changed").hexdigest()
