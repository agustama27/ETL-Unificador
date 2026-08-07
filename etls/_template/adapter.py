"""Adapter con reglas propias — completar sólo si SubprocessAdapter no alcanza.

El contrato es el Protocol ``etl_core.contracts.ETLAdapter``: ``validate``, ``command``,
``outputs`` y los flags ``stateful`` / ``requires_state_change``. Componé
``SubprocessAdapter`` para las postcondiciones en vez de reimplementarlas.
Referencia: ``etls/petersen/adapter.py``.
"""

from collections.abc import Mapping
from datetime import date
from pathlib import Path
import sys

from etl_core.contracts import SubprocessAdapter, ValidationError
from orchestrator.models import ETLDefinition, FileEvidence, RunRequest


class ClienteAdapter:
    requires_state_change = False
    stateful = False

    def __init__(self, *, today=date.today) -> None:
        self._shared = SubprocessAdapter(today=today)
        self._today = today

    def validate(self, request: RunRequest) -> None:
        # Deliberado (ADR-001, decisión 7): no existe reproceso de días caídos y los
        # legacy estampan la fecha del sistema en los nombres de salida.
        if request.business_date != self._today():
            raise ValidationError("business date must equal host-local today")
        if set(request.inputs) - {"base"}:
            raise ValidationError("unexpected extra inputs")
        if request.params:
            raise ValidationError("unexpected parameters")

    def command(
        self, definition: ETLDefinition, request: RunRequest, run: Path
    ) -> tuple[str, ...]:
        self.validate(request)
        return (
            sys.executable,
            definition.command[1],
            "--input", str(run / "input/base.csv"),
            "--output_dir", str(run / "output"),
        )

    def outputs(
        self,
        definition: ETLDefinition,
        before: Mapping[Path, FileEvidence],
        after: Mapping[Path, FileEvidence],
    ) -> tuple[FileEvidence, ...]:
        return self._shared.outputs(definition, before, after)
