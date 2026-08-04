from collections.abc import Mapping
from datetime import date
from pathlib import Path
import sys

from adapters.naranjax.ma_chat import MaChatAdapter, ValidationError
from orchestrator.models import ETLDefinition, FileEvidence, RunRequest


class MaVoicePctAdapter:
    requires_state_change = False
    stateful = False

    def __init__(self, *, today=date.today) -> None:
        self._shared = MaChatAdapter(today=today)
        self._today = today

    def validate(self, request: RunRequest) -> None:
        if request.business_date != self._today():
            raise ValidationError("business date must equal host-local today")
        if request.planes is not None or request.pagos is not None or request.no_planes_today:
            raise ValidationError("PCT accepts no PLANES, PAGOS, or no-PLANES intent")
        if request.extras:
            raise ValidationError("PCT accepts no extra inputs")

    def command(
        self, definition: ETLDefinition, request: RunRequest, run: Path
    ) -> tuple[str, ...]:
        self.validate(request)
        suffix = definition.inputs[0].extensions[0]
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
