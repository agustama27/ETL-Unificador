import re
from collections.abc import Iterator, Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Self

import yaml  # type: ignore[import-untyped]

from orchestrator.models import (
    ArtifactRole,
    ETLDefinition,
    InputSpec,
    OutputSpec,
    Readiness,
    RepositoryStatus,
)


class CatalogError(ValueError):
    """The catalog is malformed or unsafe."""

_FIELDS = {
    "id", "name", "repository_status", "readiness", "executable", "project_path",
    "working_dir", "entrypoint", "command", "fixed_arguments", "arguments",
    "adapter", "inputs", "outputs", "allowed_exits", "timeout_seconds",
    "request_date_format", "output_date_source", "environment_allowlist",
}
_REQUIRED = {"id", "name", "repository_status", "readiness", "executable", "project_path"}
_DATE_FORMATS = {"YYYYMMDD", "YYMMDD"}
_ENVIRONMENT_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class Catalog:
    def __init__(self, definitions: tuple[ETLDefinition, ...]) -> None:
        self._definitions = definitions
        self._by_id = {item.id: item for item in definitions}

    def __iter__(self) -> Iterator[ETLDefinition]:
        return iter(self._definitions)

    def __getitem__(self, etl_id: str) -> ETLDefinition:
        try:
            return self._by_id[etl_id]
        except KeyError as error:
            raise CatalogError(f"unknown ETL id: {etl_id}") from error

    @classmethod
    def load(cls, path: Path, workspace: Path, *,
             adapters: Mapping[str, object] | None = None) -> Self:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise CatalogError(f"cannot load catalog: {error}") from error
        if not isinstance(raw, dict):
            raise CatalogError("catalog root must be a mapping")
        if set(raw) != {"schema_version", "etls"}:
            raise CatalogError("catalog root has unknown or required fields")
        if raw["schema_version"] != 1 or isinstance(raw["schema_version"], bool):
            raise CatalogError("schema_version must be 1")
        if not isinstance(raw["etls"], list):
            raise CatalogError("etls must be a list")
        definitions = tuple(_definition(item, workspace.resolve(), adapters or {}) for item in raw["etls"])
        ids = [item.id for item in definitions]
        if len(ids) != len(set(ids)):
            raise CatalogError("duplicate ETL id")
        return cls(definitions)

    @classmethod
    def load_directory(cls, directory: Path, workspace: Path, *,
                       adapters: Mapping[str, object] | None = None) -> Self:
        files = sorted(directory.glob("*.yaml"))
        if not files:
            raise CatalogError(f"no catalog files found in: {directory}")
        definitions: list[ETLDefinition] = []
        for file in files:
            definitions.extend(cls.load(file, workspace, adapters=adapters))
        ids = [item.id for item in definitions]
        if len(ids) != len(set(ids)):
            raise CatalogError("duplicate ETL id across catalog files")
        return cls(tuple(definitions))


def _definition(raw: object, workspace: Path, adapters: Mapping[str, object]) -> ETLDefinition:
    if not isinstance(raw, dict):
        raise CatalogError("each ETL must be a mapping")
    unknown = set(raw) - _FIELDS
    missing = _REQUIRED - set(raw)
    if unknown:
        raise CatalogError(f"unknown ETL fields: {sorted(unknown)}")
    if missing:
        raise CatalogError(f"required ETL fields missing: {sorted(missing)}")
    for key in ("id", "name"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise CatalogError(f"{key} must be a non-empty string")
    if type(raw["executable"]) is not bool:
        raise CatalogError("executable must be a boolean")
    try:
        repository_status = RepositoryStatus(raw["repository_status"])
    except (TypeError, ValueError) as error:
        raise CatalogError("invalid repository_status") from error
    try:
        readiness = Readiness(raw["readiness"])
    except (TypeError, ValueError) as error:
        raise CatalogError("invalid readiness") from error
    values: dict[str, Any] = {
        "id": raw["id"], "name": raw["name"],
        "repository_status": repository_status, "readiness": readiness,
        "executable": raw["executable"],
        "project_path": _relative(raw["project_path"], "project_path", workspace),
    }
    for field in ("working_dir", "entrypoint"):
        if field in raw:
            values[field] = _relative(raw[field], field, workspace)
    for field in ("command", "fixed_arguments", "environment_allowlist"):
        values[field] = _strings(raw.get(field, []), field)
    arguments = raw.get("arguments", {})
    if not isinstance(arguments, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in arguments.items()
    ):
        raise CatalogError("arguments must map strings to strings")
    values["arguments"] = arguments
    values["inputs"] = _inputs(raw.get("inputs", []))
    values["outputs"] = _outputs(raw.get("outputs", []))
    exits = raw.get("allowed_exits", [])
    if not isinstance(exits, list) or not all(type(item) is int for item in exits):
        raise CatalogError("allowed_exits must contain integers")
    values["allowed_exits"] = tuple(exits)
    timeout = raw.get("timeout_seconds")
    if timeout is not None and (type(timeout) is not int or timeout <= 0):
        raise CatalogError("timeout_seconds must be positive")
    values["timeout_seconds"] = timeout
    for field in ("request_date_format", "output_date_source", "adapter"):
        value = raw.get(field)
        if value is not None and not isinstance(value, str):
            raise CatalogError(f"{field} must be a string")
        values[field] = value
    if values["request_date_format"] not in (None, *_DATE_FORMATS):
        raise CatalogError("invalid request_date_format")
    if values["output_date_source"] not in (None, "system_date"):
        raise CatalogError("invalid output_date_source")
    if not all(_ENVIRONMENT_NAME.fullmatch(name) for name in values["environment_allowlist"]):
        raise CatalogError("invalid environment name")
    if values["executable"] and (
        readiness is not Readiness.READY
        or not values["adapter"]
        or values["adapter"] not in adapters
        or not values.get("entrypoint")
        or not values["command"]
        or not values["inputs"]
        or not values["outputs"]
        or not values["allowed_exits"]
        or timeout is None
    ):
        raise CatalogError("executable ETL requires ready registered adapter and complete metadata")
    return ETLDefinition(**values)


def _relative(raw: object, field: str, workspace: Path) -> Path:
    if not isinstance(raw, str) or not raw:
        raise CatalogError(f"{field} must be a relative path")
    value = Path(raw)
    if value.is_absolute() or workspace not in (workspace / value).resolve().parents:
        raise CatalogError(f"{field} must remain within workspace")
    return value


def _relative_pattern(raw: object, field: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise CatalogError(f"{field} must be a relative pattern")
    if any(path.anchor or ".." in path.parts for path in (PurePosixPath(raw), PureWindowsPath(raw))):
        raise CatalogError(f"{field} must remain relative and contained")
    return raw

def _strings(raw: object, field: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not all(isinstance(item, str) and item for item in raw):
        raise CatalogError(f"{field} must contain strings")
    return tuple(raw)


def _inputs(raw: object) -> tuple[InputSpec, ...]:
    if not isinstance(raw, list):
        raise CatalogError("inputs must be a list")
    items: list[InputSpec] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"role", "extensions", "required"}:
            raise CatalogError("input has unknown or required fields")
        extensions = _strings(item["extensions"], "extensions")
        if not extensions or not all(value.startswith(".") for value in extensions):
            raise CatalogError("extensions must be non-empty dotted suffixes")
        if not isinstance(item["role"], str) or type(item["required"]) is not bool:
            raise CatalogError("invalid input role or required flag")
        items.append(InputSpec(item["role"], extensions, item["required"]))
    if len({item.role for item in items}) != len(items):
        raise CatalogError("duplicate input role")
    return tuple(items)


def _outputs(raw: object) -> tuple[OutputSpec, ...]:
    if not isinstance(raw, list):
        raise CatalogError("outputs must be a list")
    items: list[OutputSpec] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"role", "glob", "date_format"}:
            raise CatalogError("output has unknown or required fields")
        try:
            role = ArtifactRole(item["role"])
        except (TypeError, ValueError) as error:
            raise CatalogError("invalid output role") from error
        if item["date_format"] not in _DATE_FORMATS:
            raise CatalogError("invalid output date_format")
        items.append(OutputSpec(role, _relative_pattern(item["glob"], "output glob"), item["date_format"]))
    if len({item.role for item in items}) != len(items):
        raise CatalogError("duplicate output role")
    return tuple(items)
