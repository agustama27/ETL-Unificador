import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from orchestrator.models import RunStatus
from orchestrator.run_store import RunBlockedError, RunStore


NOW = datetime(2026, 7, 21, 14, 30, tzinfo=timezone.utc)
DAY = date(2026, 7, 21)


def store(tmp_path: Path, **overrides: Any) -> RunStore:
    options: dict[str, Any] = {
        "now": lambda: NOW,
        "uuid_factory": iter((str(i) for i in range(20))).__next__,
    }
    options.update(overrides)
    return RunStore(tmp_path / "runs", tmp_path / "state", **options)


def test_run_metadata_create_and_overwrite_fsync_file_and_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_syncs: list[int] = []
    directory_syncs: list[Path] = []
    replacements: list[tuple[Path, Path, bool]] = []
    monkeypatch.setattr(os, "fsync", file_syncs.append)
    def replace(source: Path, target: Path) -> None:
        replacements.append((source, target, target.exists()))
        source.replace(target)
    run_store = store(
        tmp_path, replace=replace, directory_fsync=directory_syncs.append
    )
    run = run_store.create_run("naranjax.ma.chat.daily")
    run_store.write_metadata(run, {"status": RunStatus.PREPARING, "day": DAY})
    run_store.write_metadata(run, {"status": RunStatus.SUCCEEDED, "day": DAY})

    assert json.loads((run / "run.json").read_text("utf-8")) == {
        "day": "2026-07-21",
        "schema": 1,
        "status": "succeeded",
    }
    assert [item[2] for item in replacements] == [False, True]
    assert all(source.parent == target.parent == run for source, target, _ in replacements)
    assert len(file_syncs) == 2
    assert directory_syncs == [run, run]


def test_failed_metadata_replace_preserves_previous_document(tmp_path: Path) -> None:
    run_store = store(tmp_path)
    run = run_store.create_run("etl")
    run_store.write_metadata(run, {"status": RunStatus.PREPARING})
    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("replace failed")
    failing_store = store(tmp_path, replace=fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        failing_store.write_metadata(run, {"status": RunStatus.SUCCEEDED})

    assert json.loads((run / "run.json").read_text("utf-8"))["status"] == "preparing"
    assert list(run.glob("*.tmp")) == []


def test_lock_collision_fails_fast_and_preserves_stale_owner(tmp_path: Path) -> None:
    run_store = store(tmp_path)
    first = run_store.acquire_lock("etl", "202607", "run-1")
    with pytest.raises(RunBlockedError) as error:
        run_store.acquire_lock("etl", "202607", "run-2")
    owner = json.loads((first.owner / "owner.json").read_text("utf-8"))
    assert error.value.code == "lock_exists"
    assert owner["run_id"] == "run-1"
    assert first.path.is_dir()


def test_release_rejects_foreign_ownership_without_deleting_it(tmp_path: Path) -> None:
    run_store = store(tmp_path)
    owned = run_store.acquire_lock("etl", "202607", "run-1")
    owned.owner.joinpath("owner.json").unlink()
    owned.owner.rmdir()
    foreign = owned.path / "foreign-token"
    foreign.mkdir()
    foreign.joinpath("owner.json").write_text('{"run_id":"foreign"}', encoding="utf-8")
    assert run_store.release_lock(owned) is False
    evidence = next(owned.path.parent.rglob("foreign-token/owner.json"))
    assert evidence.read_text("utf-8") == '{"run_id":"foreign"}'


def test_release_preserves_same_path_foreign_owner_replacement(tmp_path: Path) -> None:
    run_store = store(tmp_path)
    owned = run_store.acquire_lock("etl", "202607", "run-1")
    owner_file = owned.owner / "owner.json"
    foreign = json.loads(owner_file.read_text("utf-8"))
    foreign.update(run_id="foreign", token="foreign-token")
    owner_file.write_text(json.dumps(foreign), encoding="utf-8")

    assert run_store.release_lock(owned) is False
    evidence = list(owned.path.parent.rglob("owner.json"))
    assert [json.loads(path.read_text("utf-8"))["token"] for path in evidence] == ["foreign-token"]


def test_release_race_preserves_foreign_owner_added_during_teardown(tmp_path: Path) -> None:
    calls: list[Path] = []
    def racing_rmdir(path: Path) -> None:
        calls.append(path)
        path.rmdir()
        if len(calls) == 1:
            foreign = path.parent / "replacement-token"
            foreign.mkdir()
            foreign.joinpath("owner.json").write_text("foreign", encoding="utf-8")
    run_store = store(tmp_path, remove_directory=racing_rmdir)
    owned = run_store.acquire_lock("etl", "202607", "run-1")
    assert run_store.release_lock(owned) is False
    evidence = next(owned.path.parent.glob(".lock.release-*/replacement-token/owner.json"))
    assert evidence.read_text("utf-8") == "foreign"


def test_owned_release_removes_only_its_lock_directory(tmp_path: Path) -> None:
    run_store = store(tmp_path)
    owned = run_store.acquire_lock("etl", "202607", "run-1")
    assert run_store.release_lock(owned) is True
    assert not owned.path.exists()


def test_release_preserves_generic_lock_acquired_after_claim(tmp_path: Path) -> None:
    generic = tmp_path / "state/etl/202607/.lock/generic"
    attempts: list[Path] = []
    def replace(source: Path, target: Path) -> None:
        attempts.append(source)
        if len(attempts) == 1:
            raise PermissionError("lock temporarily busy")
        source.replace(target)
        generic.parent.mkdir()
        generic.write_text("foreign", encoding="utf-8")
    run_store = store(tmp_path, replace=replace)
    owned = run_store.acquire_lock("etl", "202607", "run-1")
    assert run_store.release_lock(owned) is True
    assert generic.read_text("utf-8") == "foreign"
    assert 2 <= len(attempts) <= 4
