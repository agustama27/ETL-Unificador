from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class EtlConfig:
    output_dir: Path
    log_dir: Path
    config_path: Path | None = None
    run_date: date | None = None
    strict: bool = False


@dataclass(frozen=True)
class InputFiles:
    raw_input: Path


@dataclass(frozen=True)
class EtlResult:
    ok: bool
    valid_records: int
    issues: int
    paths: dict[str, Path] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_legacy_dict(self) -> dict:
        return {"paths": self.paths, "valid_records": self.valid_records, "issues": self.issues}
