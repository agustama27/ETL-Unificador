import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
import sys

from etl_core.contracts import SubprocessAdapter, ValidationError
from orchestrator.models import ETLDefinition, FileEvidence, RunRequest


class PetersenBaseAdapter:
    """Directory-in adapter for the 4-bank tabla integradora generator.

    The legacy discovers files by NAME (leading YYYYMMDD + bank code
    BER/BSF/BSJ/BSC + kind keyword) inside one folder, so staging must
    preserve original filenames and the command passes the directory.
    """

    requires_state_change = False
    stateful = False

    ROLES = frozenset(
        {"base", "deelo_1"}
        | {f"integracion_{n}" for n in (2, 3, 4)}
        | {f"deelo_{n}" for n in (2, 3, 4)}
        | {f"mailcli_{n}" for n in (1, 2, 3, 4)}
    )
    BANKS = ("BER", "BSF", "BSJ", "BSC")
    NAME_PATTERN = re.compile(r"^\d{8}_.*", re.IGNORECASE)

    def __init__(self, *, today=date.today) -> None:
        self._shared = SubprocessAdapter(today=today)
        self._today = today

    @classmethod
    def _classify_name(cls, name: str) -> tuple[str, str, str] | None:
        upper = name.upper()
        if not cls.NAME_PATTERN.match(name):
            return None
        bank = next((code for code in cls.BANKS if code in upper), None)
        if bank is None:
            return None
        if "INTEGRACION" in upper:
            kind = "integracion"
        elif "DEELO" in upper:
            kind = "deelo"
        elif "MAILCLI" in upper:
            kind = "mailcli"
        else:
            return None
        return name[:8], bank, kind

    def validate(self, request: RunRequest) -> None:
        # Deliberado (ADR-001, decisión 7): no existe reproceso de días caídos.
        if request.business_date != self._today():
            raise ValidationError("business date must equal host-local today")
        if request.params:
            raise ValidationError("base accepts no parameters")
        unknown = set(request.inputs) - self.ROLES
        if unknown:
            raise ValidationError(f"unknown base inputs: {sorted(unknown)}")
        missing = {"base", "deelo_1"} - set(request.inputs)
        if missing:
            raise ValidationError(f"missing base inputs: {sorted(missing)}")

        dates: set[str] = set()
        banks: dict[str, set[str]] = {}
        for role, source in request.inputs.items():
            classified = self._classify_name(source.name)
            if classified is None:
                raise ValidationError(
                    f"{role}: el nombre '{source.name}' debe empezar con YYYYMMDD y "
                    "contener banco (BER/BSF/BSJ/BSC) y tipo "
                    "(INTEGRACION/PRODCLI_DEELO/MAILCLI); el legacy lo ignoraría en silencio")
            day, bank, kind = classified
            dates.add(day)
            banks.setdefault(bank, set()).add(kind)
        if len(dates) > 1:
            raise ValidationError(
                f"todos los archivos deben compartir la misma fecha YYYYMMDD; vinieron {sorted(dates)}")
        for bank, kinds in sorted(banks.items()):
            if "integracion" in kinds and "deelo" not in kinds:
                raise ValidationError(
                    f"el banco {bank} tiene INTEGRACION sin su PRODCLI_DEELO")
            if "deelo" in kinds and "integracion" not in kinds:
                raise ValidationError(
                    f"el banco {bank} tiene PRODCLI_DEELO sin su INTEGRACION")

    def input_destination(self, role: str, source: Path) -> Path:
        # El legacy descubre banco+fecha desde el nombre: renombrar lo rompe.
        return Path("input/incoming") / source.name

    def command(
        self, definition: ETLDefinition, request: RunRequest, run: Path
    ) -> tuple[str, ...]:
        self.validate(request)
        return (
            sys.executable,
            definition.command[1],
            "--input", str(run / "input/incoming"),
            "--output_dir", str(run / "output"),
        )

    def outputs(
        self,
        definition: ETLDefinition,
        before: Mapping[Path, FileEvidence],
        after: Mapping[Path, FileEvidence],
    ) -> tuple[FileEvidence, ...]:
        return self._shared.outputs(definition, before, after)
