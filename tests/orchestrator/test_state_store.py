import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from orchestrator.run_store import RunBlockedError
from orchestrator.state_store import DirectoryApi, StatePromotionError, StateStore, _fsync_directory


DAY = date(2026, 7, 21)
ETL = "naranjax.ma.chat.daily"


def staged(tmp_path: Path, content: str = "new-state") -> Path:
    path = tmp_path / "run/state/estado_202607.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def lineage(tmp_path: Path) -> Path:
    return tmp_path / "canonical" / ETL / "202607"


def store(tmp_path: Path, **overrides: Any) -> StateStore:
    ids = iter((str(i) for i in range(20))).__next__
    return StateStore(tmp_path / "canonical", uuid_factory=ids, **overrides)


def directory_api(events: list[tuple[str, object]], failure: str = "") -> DirectoryApi:
    def record(name: str, value: object) -> None:
        events.append((name, value))
        if name == failure:
            raise OSError(f"{name} failed")
    def open_directory(path: Path) -> int:
        record("open", path)
        return 7
    return open_directory, lambda handle: record("flush", handle), lambda handle: record("close", handle)


def test_directory_fsync_retains_posix_open_flush_close_order() -> None:
    events: list[tuple[str, object]] = []
    _fsync_directory(Path("state"), platform="posix", api=directory_api(events))
    assert events == [("open", Path("state")), ("flush", 7), ("close", 7)]


@pytest.mark.parametrize(
    ("failure", "expected"), [("open", ["open"]), ("flush", ["open", "flush", "close"])],
)
def test_windows_directory_fsync_orders_calls_and_propagates_errors(
    failure: str, expected: list[str]
) -> None:
    events: list[tuple[str, object]] = []
    with pytest.raises(OSError, match=f"{failure} failed"):
        _fsync_directory(Path("state"), platform="nt", api=directory_api(events, failure))
    assert [name for name, _ in events] == expected


def test_promotion_order_and_fsyncs(tmp_path: Path) -> None:
    events: list[tuple[str, str]] = []
    def replace(source: Path, target: Path) -> None:
        assert source.parent == target.parent
        events.append(("replace", target.name))
        source.replace(target)
    state_store = store(
        tmp_path,
        replace=replace,
        file_fsync=lambda _: events.append(("fsync-file", "temporary")),
        directory_fsync=lambda path: events.append(("fsync-dir", path.name)),
    )
    result = state_store.promote(ETL, DAY, staged(tmp_path), "run-1")
    assert result.snapshot.read_text("utf-8") == "new-state"
    assert result.current.read_text("utf-8") == "new-state"
    replacements = [event for event in events if event[0] == "replace"]
    assert replacements == [
        ("replace", "estado_20260721.csv"),
        ("replace", "estado_202607.csv"),
    ]
    assert [event[0] for event in events] == ["fsync-file", "replace", "fsync-dir"] * 2


@pytest.mark.parametrize("blocker", ["snapshot", "recovery.json", "recovery_required"])
def test_preflight_blockers_prevent_both_state_writes(tmp_path: Path, blocker: str) -> None:
    root = lineage(tmp_path)
    root.mkdir(parents=True)
    current = root / "estado_202607.csv"
    current.write_text("old-state", encoding="utf-8")
    target = root / ("estado_20260721.csv" if blocker == "snapshot" else blocker)
    if blocker == "recovery_required":
        target.mkdir()
    else:
        target.write_text("evidence", "utf-8")
    writes: list[object] = []
    state_store = store(tmp_path, replace=lambda _, b: writes.append(b),
                        file_fsync=writes.append)
    with pytest.raises(RunBlockedError) as error:
        state_store.promote(ETL, DAY, staged(tmp_path), "run-2")
    expected = "snapshot_exists" if blocker == "snapshot" else "recovery_required"
    assert error.value.code == expected
    assert writes == []
    assert current.read_text("utf-8") == "old-state"
    assert list(root.glob("*.tmp")) == []


def test_current_failure_persists_primary_recovery(tmp_path: Path) -> None:
    calls = 0
    def replace(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("current unavailable")
        source.replace(target)
    with pytest.raises(StatePromotionError) as error:
        store(tmp_path, replace=replace).promote(ETL, DAY, staged(tmp_path), "run-3")
    root = lineage(tmp_path)
    evidence = json.loads((root / "recovery.json").read_text("utf-8"))
    assert error.value.code == "recovery_required"
    assert evidence["run_id"] == "run-3"
    assert evidence["business_date"] == "20260721"
    assert evidence["snapshot"] == "estado_20260721.csv"
    assert (root / evidence["snapshot"]).read_text("utf-8") == "new-state"
    assert not (root / "estado_202607.csv").exists()


def test_primary_recovery_failure_uses_fsynced_fallback(tmp_path: Path) -> None:
    synced_files: list[int] = []
    synced_directories: list[Path] = []
    def replace(source: Path, target: Path) -> None:
        if target.name in {"estado_202607.csv", "recovery.json"}:
            raise OSError(f"cannot replace {target.name}")
        source.replace(target)
    state_store = store(
        tmp_path,
        replace=replace,
        file_fsync=synced_files.append,
        directory_fsync=synced_directories.append,
    )
    with pytest.raises(StatePromotionError) as error:
        state_store.promote(ETL, DAY, staged(tmp_path), "run-4")
    fallback = next(lineage(tmp_path).glob("recovery_required/*.json"))
    assert error.value.code == "recovery_required"
    assert json.loads(fallback.read_text("utf-8"))["run_id"] == "run-4"
    assert len(synced_files) == 4
    assert synced_directories[-2:] == [fallback.parent, fallback.parent.parent]
    with pytest.raises(RunBlockedError, match="recovery"):
        state_store.promote(ETL, DAY, staged(tmp_path, "retry"), "run-5")


def test_snapshot_fsync_failure_is_typed_without_state_writes(tmp_path: Path) -> None:
    def fail_fsync(_: int) -> None:
        raise OSError("disk sync failed")
    with pytest.raises(StatePromotionError) as error:
        store(tmp_path, file_fsync=fail_fsync).promote(ETL, DAY, staged(tmp_path), "run-6")
    assert error.value.code == "promotion_failed"
    assert not (lineage(tmp_path) / "estado_20260721.csv").exists()
    assert list(lineage(tmp_path).glob("*.tmp")) == []
