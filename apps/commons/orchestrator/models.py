from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


class RepositoryStatus(StrEnum):
    PRESENT = "present"


class Readiness(StrEnum):
    CANDIDATE = "candidate"
    BLOCKED = "blocked"
    READY = "ready"


class RunStatus(StrEnum):
    PREPARING = "preparing"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    BLOCKED = "blocked"


class StateStatus(StrEnum):
    NOT_STARTED = "not_started"
    STAGED = "staged"
    PROMOTED = "promoted"
    RECOVERY_REQUIRED = "recovery_required"


class ArtifactRole(StrEnum):
    """Transitional: output roles are open strings validated by the catalog.

    Kept only so pre-Fase-2 imports keep resolving; do not add members.
    """

    ROMAN = "roman"
    CHAT = "chat"
    E1KIA = "e1kia"
    PCT = "pct"
    ANOMALIES = "anomalies"
    SURVEY_BASE = "survey_base"
    SURVEY_BASE_E164 = "survey_base_e164"
    BASE_FILTRADA = "base_filtrada"
    TELEFONOS = "telefonos"
    GESTIONES = "gestiones"
    LEGACY_LOG = "legacy_log"


@dataclass(frozen=True)
class InputSpec:
    role: str
    extensions: tuple[str, ...]
    required: bool


@dataclass(frozen=True)
class OutputSpec:
    role: str
    glob: str
    date_format: str | None = None


@dataclass(frozen=True)
class ETLDefinition:
    id: str
    name: str
    repository_status: RepositoryStatus
    readiness: Readiness
    executable: bool
    project_path: Path
    working_dir: Path | None = None
    entrypoint: Path | None = None
    command: tuple[str, ...] = ()
    fixed_arguments: tuple[str, ...] = ()
    arguments: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    adapter: str | None = None
    inputs: tuple[InputSpec, ...] = ()
    outputs: tuple[OutputSpec, ...] = ()
    allowed_exits: tuple[int, ...] = ()
    timeout_seconds: int | None = None
    request_date_format: str | None = None
    output_date_source: str | None = None
    environment_allowlist: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class RunRequest:
    etl_id: str
    business_date: date
    inputs: Mapping[str, Path] = field(
        default_factory=lambda: MappingProxyType({})
    )
    params: Mapping[str, str | bool] = field(
        default_factory=lambda: MappingProxyType({})
    )
    environment: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))


@dataclass(frozen=True)
class FileEvidence:
    role: str
    path: Path
    size: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int | None
    timed_out: bool
    timestamps: tuple[str, str | None]


@dataclass(frozen=True)
class StateEffect:
    scope: str
    status: StateStatus


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: RunStatus
    error_code: str | None
    artifacts: tuple[FileEvidence, ...]
    state: StateEffect
