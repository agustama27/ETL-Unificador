from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]  # PyYAML does not bundle type information

from orchestrator.catalog import Catalog, CatalogError
from orchestrator.models import ArtifactRole, Readiness


def _entry(**changes: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "id": "naranjax.ma.chat.daily",
        "name": "Chat daily",
        "repository_status": "present",
        "readiness": "candidate",
        "executable": False,
        "project_path": "project",
    }
    entry.update(changes)
    return entry


def _write(tmp_path: Path, entry: dict[str, object], **root: object) -> Path:
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump({"schema_version": 1, "etls": [entry], **root}), encoding="utf-8")
    return path


def test_repository_catalog_promotes_only_daily_chat_and_voice() -> None:
    adapters = {"naranjax.ma.chat": object(), "naranjax.ma.voice": object()}
    catalog = Catalog.load(
        Path("registry/naranjax.yaml"), Path.cwd(),
        adapters=adapters,
    )

    assert tuple(item.id for item in catalog) == (
        "naranjax.ma.chat.daily", "naranjax.ma.voice.daily",
        "naranjax.ma.voice.pct", "naranjax.mt.voice.daily")
    chat = catalog["naranjax.ma.chat.daily"]
    assert (chat.readiness, chat.executable, chat.command) == (Readiness.READY, True, (
        "python", "back-base/ejecutar_dia.py",
    ))
    assert chat.arguments["business_date"] == "--fecha"
    roles = tuple(output.role for output in chat.outputs)
    assert roles == (ArtifactRole.ROMAN, ArtifactRole.CHAT, ArtifactRole.E1KIA)
    assert chat.adapter == "naranjax.ma.chat"
    voice = catalog["naranjax.ma.voice.daily"]
    assert (voice.readiness, voice.executable, voice.command) == (
        Readiness.READY, True, ("python", "back-base/ejecutar_dia.py")
    )
    assert voice.fixed_arguments == ()
    assert voice.arguments == {
        "business_date": "--fecha", "base": "--input", "planes": "--planes",
        "pagos": "--pagos", "no_planes_today": "--sin-planes-hoy",
    }
    assert tuple((item.role, item.required) for item in voice.inputs) == (
        ("base", True), ("planes", False), ("pagos", False)
    )
    assert tuple(output.role for output in voice.outputs) == (
        ArtifactRole.ROMAN, ArtifactRole.E1KIA
    )
    assert (voice.adapter, voice.allowed_exits, voice.timeout_seconds) == (
        "naranjax.ma.voice", (0,), 900
    )
    assert voice.environment_allowlist == ("NARANJAX_PLANES_MIN_COVERAGE",)
    assert all(not item.executable and item.adapter is None for item in tuple(catalog)[2:])


@pytest.mark.parametrize(
    ("root", "message"),
    [
        ({"schema_version": 2, "etls": [_entry()]}, "schema_version"),
        ({"schema_version": 1, "etls": "invalid"}, "etls"),
        ({"schema_version": 1, "etls": [_entry(), _entry()]}, "duplicate"),
        ({"schema_version": 1, "etls": [_entry(extra=True)]}, "unknown"),
        ({"schema_version": 1, "etls": [{"id": "incomplete"}]}, "required"),
    ],
)
def test_catalog_rejects_invalid_root_schema_ids_and_fields(
    tmp_path: Path, root: object, message: str
) -> None:
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(root), encoding="utf-8")

    with pytest.raises(CatalogError, match=message):
        Catalog.load(path, tmp_path)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"repository_status": "missing"}, "repository_status"),
        ({"readiness": "unknown"}, "readiness"),
        ({"executable": "false"}, "executable"),
        ({"command": ["python", 7]}, "command"),
        ({"fixed_arguments": "--chat"}, "fixed_arguments"),
        ({"arguments": {"business_date": 7}}, "arguments"),
        ({"inputs": [{"role": "base", "extensions": [], "required": True}]}, "extensions"),
        ({"outputs": [{"role": "invalid", "glob": "*.csv", "date_format": "YYMMDD"}]}, "role"),
        ({"outputs": [{"role": "chat", "glob": "*.csv", "date_format": "ISO"}]}, "date_format"),
        ({"timeout_seconds": 0}, "timeout_seconds"),
        ({"environment_allowlist": ["lower-case"]}, "environment"),
    ],
)
def test_catalog_rejects_invalid_enums_execution_and_metadata(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    with pytest.raises(CatalogError, match=message):
        Catalog.load(_write(tmp_path, _entry(**changes)), tmp_path)


@pytest.mark.parametrize("field", ["project_path", "working_dir", "entrypoint"])
@pytest.mark.parametrize("unsafe", ["../escape", str(Path.cwd().resolve())])
def test_catalog_rejects_absolute_and_escaping_paths(
    tmp_path: Path, field: str, unsafe: str
) -> None:
    with pytest.raises(CatalogError, match=field):
        Catalog.load(_write(tmp_path, _entry(**{field: unsafe})), tmp_path)


@pytest.mark.parametrize("glob", ["../../escape/*.csv", "/escape/*.csv", r"C:\escape\*.csv"])
def test_catalog_rejects_unsafe_output_globs(tmp_path: Path, glob: str) -> None:
    output = {"role": "chat", "glob": glob, "date_format": "YYMMDD"}
    with pytest.raises(CatalogError, match="output glob"):
        Catalog.load(_write(tmp_path, _entry(outputs=[output])), tmp_path)


def test_catalog_rejects_symlink_escape_and_unregistered_executable(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(CatalogError, match="project_path"):
        Catalog.load(_write(tmp_path, _entry(project_path="linked")), tmp_path)

    executable = _entry(
        readiness="ready", executable=True, adapter="missing", entrypoint="job.py",
        command=["python"], inputs=[{"role": "base", "extensions": [".xlsx"], "required": True}],
        outputs=[{"role": "chat", "glob": "*.csv", "date_format": "YYMMDD"}],
        allowed_exits=[0], timeout_seconds=900,
    )
    with pytest.raises(CatalogError, match="adapter"):
        Catalog.load(_write(tmp_path, executable), tmp_path, adapters={})
