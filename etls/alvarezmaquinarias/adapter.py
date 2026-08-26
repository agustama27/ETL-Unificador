from collections.abc import Mapping
from datetime import date
from pathlib import Path
import sys

from etl_core.contracts import SubprocessAdapter, ValidationError
from orchestrator.models import ETLDefinition, FileEvidence, RunRequest


class AlvarezMaquinariasAdapter:
    requires_state_change = False
    stateful = False

    REQUIRED_EXTRAS = {"maquinarias": "--maquinarias", "servicios": "--servicios",
                       "repuestos": "--repuestos"}
    EXTRA_SUFFIXES = {"maquinarias": ".xlsx", "servicios": ".xlsx", "repuestos": ".pdf"}

    def __init__(self, *, today=date.today) -> None:
        self._shared = SubprocessAdapter(today=today)
        self._today = today

    def validate(self, request: RunRequest) -> None:
        # Deliberado (ADR-001, decisión 7): no existe reproceso de días caídos y los
        # legacy estampan la fecha del sistema en los nombres de salida.
        if request.business_date != self._today():
            raise ValidationError("business date must equal host-local today")
        if request.params:
            raise ValidationError("cobranzas accepts no parameters")
        expected = {"base"} | set(self.REQUIRED_EXTRAS)
        missing = expected - set(request.inputs)
        if missing:
            raise ValidationError(f"missing cobranzas inputs: {sorted(missing)}")
        unknown = set(request.inputs) - expected
        if unknown:
            raise ValidationError(f"unknown cobranzas inputs: {sorted(unknown)}")
        base_suffix = request.inputs["base"].suffix.casefold()
        if base_suffix not in {".xls", ".csv"}:
            raise ValidationError(f"saldos must be .xls or .csv, got {base_suffix or '(none)'}")

    def command(
        self, definition: ETLDefinition, request: RunRequest, run: Path
    ) -> tuple[str, ...]:
        self.validate(request)
        base_suffix = request.inputs["base"].suffix.casefold()
        command = [
            sys.executable,
            definition.command[1],
            "--input", str(run / f"input/base{base_suffix}"),
            "--output_dir", str(run / "output"),
        ]
        for role in sorted(self.REQUIRED_EXTRAS):
            command.extend((self.REQUIRED_EXTRAS[role],
                            str(run / f"input/{role}{self.EXTRA_SUFFIXES[role]}")))
        return tuple(command)

    def outputs(
        self,
        definition: ETLDefinition,
        before: Mapping[Path, FileEvidence],
        after: Mapping[Path, FileEvidence],
    ) -> tuple[FileEvidence, ...]:
        return self._shared.outputs(definition, before, after)
