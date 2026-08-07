"""Shared adapter contract: the only coupling point between core and clients."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Protocol, runtime_checkable
import re
import sys

from orchestrator.models import ETLDefinition, FileEvidence, RunRequest


class ValidationError(ValueError):
    """The request cannot safely cross the legacy adapter boundary."""


class PostconditionError(RuntimeError):
    """Legacy outputs do not satisfy the adapter contract."""


@runtime_checkable
class ETLAdapter(Protocol):
    stateful: bool
    requires_state_change: bool

    def validate(self, request: RunRequest) -> None: ...

    def command(
        self, definition: ETLDefinition, request: RunRequest, run: Path
    ) -> tuple[str, ...]: ...

    def outputs(
        self,
        definition: ETLDefinition,
        before: Mapping[Path, FileEvidence],
        after: Mapping[Path, FileEvidence],
    ) -> tuple[FileEvidence, ...]: ...


class SubprocessAdapter:
    """Generic base-in, artifacts-out adapter for legacy CLIs with --input/--output_dir."""

    requires_state_change = False
    stateful = False

    def __init__(self, *, today=date.today) -> None:
        self._today = today

    def validate(self, request: RunRequest) -> None:
        # Deliberado (ADR-001, decisión 7): no existe reproceso de días caídos y los
        # legacy estampan la fecha del sistema en los nombres de salida.
        if request.business_date != self._today():
            raise ValidationError("business date must equal host-local today")
        if set(request.inputs) - {"base"}:
            raise ValidationError("adapter accepts only the base input")
        if request.params:
            raise ValidationError("adapter accepts no parameters")

    def command(
        self, definition: ETLDefinition, request: RunRequest, run: Path
    ) -> tuple[str, ...]:
        self.validate(request)
        suffix = definition.inputs[0].extensions[0]
        return (
            sys.executable,
            definition.command[1],
            *definition.fixed_arguments,
            "--input", str(run / f"input/base{suffix}"),
            "--output_dir", str(run / "output"),
        )

    def outputs(
        self,
        definition: ETLDefinition,
        before: Mapping[Path, FileEvidence],
        after: Mapping[Path, FileEvidence],
    ) -> tuple[FileEvidence, ...]:
        selected: list[FileEvidence] = []
        for output in definition.outputs:
            matches = tuple(
                item
                for item in after.values()
                if item.path.match(f"output/{output.glob}")
            )
            classification = self._classify(
                matches, before, output.date_format, self._today()
            )
            if isinstance(classification, str):
                raise PostconditionError(f"{output.role}: {classification}")
            selected.append(replace(classification, role=output.role))
        return tuple(selected)

    @staticmethod
    def _classify(
        matches: tuple[FileEvidence, ...],
        before: Mapping[Path, FileEvidence],
        date_format: str | None,
        today: date,
    ) -> FileEvidence | str:
        if not matches:
            return "missing"
        if len(matches) != 1:
            return "ambiguous"
        item = matches[0]
        if date_format is not None:
            formats = {"YYYYMMDD": "%Y%m%d", "YYMMDD": "%y%m%d", "DDMMYYYY": "%d%m%Y"}
            expected = today.strftime(formats[date_format])
            if re.search(rf"(?<!\d){expected}(?!\d)", item.path.name) is None:
                return "wrong-date"
        if before.get(item.path) == item:
            return "unchanged"
        return item
