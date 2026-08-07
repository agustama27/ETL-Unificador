from collections.abc import Mapping
from datetime import date
from pathlib import Path
import sys

from etls.naranjax.ma_chat import MaChatAdapter, ValidationError
from orchestrator.models import ETLDefinition, FileEvidence, RunRequest


class MtVoiceBackAdapter:
    requires_state_change = False
    stateful = False

    def __init__(self, *, today=date.today) -> None:
        self._shared = MaChatAdapter(today=today)
        self._today = today

    def validate(self, request: RunRequest) -> None:
        if request.business_date != self._today():
            raise ValidationError("business date must equal host-local today")
        if set(request.inputs) != {"base", "logcall", "historial"}:
            raise ValidationError("back requires exactly logcall and historial extras")
        if request.params:
            raise ValidationError("back accepts no parameters")

    def command(
        self, definition: ETLDefinition, request: RunRequest, run: Path
    ) -> tuple[str, ...]:
        self.validate(request)
        return (
            sys.executable,
            definition.command[1],
            "--back",
            "--logcall", str(run / "input/logcall.csv"),
            "--historial", str(run / "input/historial.csv"),
            "--m30", str(run / "input/base.txt"),
            "--back-output-dir", str(run / "output"),
        )

    def outputs(
        self,
        definition: ETLDefinition,
        before: Mapping[Path, FileEvidence],
        after: Mapping[Path, FileEvidence],
    ) -> tuple[FileEvidence, ...]:
        return self._shared.outputs(definition, before, after)
