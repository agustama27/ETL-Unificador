from collections.abc import Mapping
from datetime import date
from pathlib import Path
import sys

from etl_core.contracts import SubprocessAdapter, ValidationError
from orchestrator.models import ETLDefinition, FileEvidence, RunRequest


class CartaSurAdapter:
    """Base-in adapter that honors the real staged suffix (.xlsx/.xlsm/.csv).

    The generic ``SubprocessAdapter`` hardcodes ``inputs[0].extensions[0]``
    while the service stages the real upload suffix, so with more than one
    declared extension the command would point at a nonexistent file.
    """

    requires_state_change = False
    stateful = False

    ALLOWED = {".xlsx", ".xlsm", ".csv"}

    def __init__(self, *, today=date.today) -> None:
        self._shared = SubprocessAdapter(today=today)

    def validate(self, request: RunRequest) -> None:
        self._shared.validate(request)
        suffix = request.inputs["base"].suffix.casefold()
        if suffix not in self.ALLOWED:
            raise ValidationError(
                f"base must be .xlsx, .xlsm or .csv, got {suffix or '(none)'}")

    def command(
        self, definition: ETLDefinition, request: RunRequest, run: Path
    ) -> tuple[str, ...]:
        self.validate(request)
        suffix = request.inputs["base"].suffix.casefold()
        return (
            sys.executable,
            definition.command[1],
            "--input", str(run / f"input/base{suffix}"),
            "--output_dir", str(run / "output"),
        )

    def outputs(
        self,
        definition: ETLDefinition,
        before: Mapping[Path, FileEvidence],
        after: Mapping[Path, FileEvidence],
    ) -> tuple[FileEvidence, ...]:
        return self._shared.outputs(definition, before, after)
