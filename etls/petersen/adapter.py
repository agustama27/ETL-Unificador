from collections.abc import Mapping
from datetime import date
from pathlib import Path
import sys

from etl_core.contracts import SubprocessAdapter, ValidationError
from orchestrator.models import ETLDefinition, FileEvidence, RunRequest


class PetersenGestionesAdapter:
    requires_state_change = False
    stateful = False

    OPTIONAL_EXTRAS = {"approach": "--approach", "clientes": "--clientes",
                       "excluidos": "--excluidos"}

    def __init__(self, *, today=date.today) -> None:
        self._shared = SubprocessAdapter(today=today)
        self._today = today

    def validate(self, request: RunRequest) -> None:
        if request.business_date != self._today():
            raise ValidationError("business date must equal host-local today")
        if request.params:
            raise ValidationError("gestiones accepts no parameters")
        unknown = set(request.inputs) - {"base"} - set(self.OPTIONAL_EXTRAS)
        if unknown:
            raise ValidationError(f"unknown gestiones extras: {sorted(unknown)}")

    def command(
        self, definition: ETLDefinition, request: RunRequest, run: Path
    ) -> tuple[str, ...]:
        self.validate(request)
        command = [
            sys.executable,
            definition.command[1],
            "--input", str(run / "input/base.csv"),
            "--output_dir", str(run / "output"),
        ]
        for role in sorted(set(request.inputs) - {"base"}):
            command.extend((self.OPTIONAL_EXTRAS[role], str(run / f"input/{role}.csv")))
        return tuple(command)

    def outputs(
        self,
        definition: ETLDefinition,
        before: Mapping[Path, FileEvidence],
        after: Mapping[Path, FileEvidence],
    ) -> tuple[FileEvidence, ...]:
        return self._shared.outputs(definition, before, after)
