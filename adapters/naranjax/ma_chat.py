from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from pathlib import Path
import re
import sys

from orchestrator.models import ETLDefinition, FileEvidence, RunRequest


class ValidationError(ValueError):
    """The request cannot safely cross the legacy adapter boundary."""


class PostconditionError(RuntimeError):
    """Legacy outputs do not satisfy the adapter contract."""


class MaChatAdapter:
    requires_state_change = False
    stateful = True

    def __init__(self, *, today=date.today) -> None:
        self._today = today

    def validate(self, request: RunRequest) -> None:
        if request.business_date != self._today():
            raise ValidationError("business date must equal host-local today")
        if request.extras:
            raise ValidationError("unexpected extra inputs")
        if request.planes is None and not request.no_planes_today:
            raise ValidationError("omitted PLANES requires no_planes_today")
        if request.planes is not None and request.no_planes_today:
            raise ValidationError("PLANES conflicts with no_planes_today")

    def command(
        self, definition: ETLDefinition, request: RunRequest, run: Path
    ) -> tuple[str, ...]:
        self.validate(request)
        daily = run / "input/diarios"
        if request.planes is None and any(daily.iterdir()):
            raise ValidationError("daily directory must be empty without PLANES")
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
        if request.planes is None:
            command.append("--sin_planes_hoy")
        else:
            command.extend(("--planes", str(daily / "planes.xlsx")))
        if request.pagos is not None:
            command.extend(("--pagos", str(daily / "pagos.csv")))
        command.append("--chat")
        return tuple(command)

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
                raise PostconditionError(f"{output.role.value}: {classification}")
            selected.append(replace(classification, role=output.role))
        return tuple(selected)

    @staticmethod
    def _classify(
        matches: tuple[FileEvidence, ...],
        before: Mapping[Path, FileEvidence],
        date_format: str,
        today: date,
    ) -> FileEvidence | str:
        if not matches:
            return "missing"
        if len(matches) != 1:
            return "ambiguous"
        item = matches[0]
        expected = today.strftime("%Y%m%d" if date_format == "YYYYMMDD" else "%y%m%d")
        if re.search(rf"(?<!\d){expected}(?!\d)", item.path.name) is None:
            return "wrong-date"
        if before.get(item.path) == item:
            return "unchanged"
        return item
