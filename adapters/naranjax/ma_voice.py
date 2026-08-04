from collections.abc import Mapping
from datetime import date
from pathlib import Path
import sys

from adapters.naranjax.ma_chat import MaChatAdapter, ValidationError
from orchestrator.models import ETLDefinition, FileEvidence, RunRequest


class MaVoiceAdapter:
    requires_state_change = True
    stateful = True

    def __init__(self, *, today=date.today) -> None:
        self._shared = MaChatAdapter(today=today)

    def validate(self, request: RunRequest) -> None:
        self._shared.validate(request)

    def command(
        self, definition: ETLDefinition, request: RunRequest, run: Path
    ) -> tuple[str, ...]:
        self.validate(request)
        daily = run / "input/diarios"
        expected = {
            daily / name
            for supplied, name in (
                (request.planes, "planes.xlsx"),
                (request.pagos, "pagos.csv"),
            )
            if supplied is not None
        }
        if set(daily.iterdir()) != expected:
            raise ValidationError("daily directory must contain exactly staged PLANES/PAGOS")

        day = request.business_date.strftime("%Y%m%d")
        command = [
            sys.executable,
            definition.command[1],
            "--fecha", day,
            "--mes", day[:6],
            "--input", str(run / "input/base.xlsx"),
            "--diarios_dir", str(daily),
            "--estado_dir", str(run / "state"),
            "--output_dir", str(run / "output"),
            "--logs_dir", str(run / "logs"),
            "--procesados_dir", str(run / "processed"),
        ]
        if request.planes is not None:
            command.extend(("--planes", str(daily / "planes.xlsx")))
        if request.pagos is not None:
            command.extend(("--pagos", str(daily / "pagos.csv")))
        return tuple(command)

    def outputs(
        self,
        definition: ETLDefinition,
        before: Mapping[Path, FileEvidence],
        after: Mapping[Path, FileEvidence],
    ) -> tuple[FileEvidence, ...]:
        return self._shared.outputs(definition, before, after)
