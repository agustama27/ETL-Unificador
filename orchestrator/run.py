from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol

from etl_core.contracts import ETLAdapter

from .catalog import Catalog, CatalogError, adapter_for
from .models import ETLDefinition, RunRequest, RunResult, RunStatus
from .run_store import RunStore
from .runner import Runner
from .service import RunService
from .state_store import StateStore


class Service(Protocol):
    def execute(self, request: RunRequest) -> RunResult: ...


ServiceFactory = Callable[[ETLDefinition, ETLAdapter], Service]


def _business_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a real date in YYYYMMDD format") from error


def _extra_input(value: str) -> tuple[str, Path]:
    role, separator, path = value.partition("=")
    if not separator or not role.strip() or not path.strip():
        raise argparse.ArgumentTypeError("must use ROLE=PATH format")
    return role.strip(), Path(path.strip())


def _param(value: str) -> tuple[str, str | bool]:
    name, separator, raw = value.partition("=")
    if not name.strip():
        raise argparse.ArgumentTypeError("must use NAME or NAME=VALUE format")
    if not separator:
        return name.strip(), True
    return name.strip(), raw.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a guarded ETL from the unifier catalog.")
    parser.add_argument("--etl", required=True)
    parser.add_argument("--fecha", required=True, type=_business_date, metavar="YYYYMMDD")
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--input", action="append", type=_extra_input, default=[],
                        metavar="ROLE=PATH", dest="inputs")
    parser.add_argument("--param", action="append", type=_param, default=[],
                        metavar="NAME[=VALUE]", dest="params")
    return parser


def _service(definition: ETLDefinition, workspace: Path, adapter: ETLAdapter) -> RunService:
    state_root = workspace / "var/state"
    return RunService(
        definition, adapter, Runner(), RunStore(workspace / "var/runs", state_root),
        StateStore(state_root), workspace=workspace,
        now=lambda: datetime.now(timezone.utc).isoformat(),
    )


def main(argv: Sequence[str] | None = None, *, adapters: Mapping[str, ETLAdapter] | None = None,
         service_factory: ServiceFactory | None = None) -> int:
    arguments = _parser().parse_args(argv)
    workspace = Path(__file__).resolve().parents[1]
    definition = Catalog.load_directory(workspace / "registry", workspace,
                                        adapters=adapters)[arguments.etl]
    if not definition.executable or definition.adapter is None:
        raise CatalogError(f"ETL is not executable: {definition.id}")
    adapter = adapter_for(definition, adapters)
    service = (service_factory(definition, adapter) if service_factory
               else _service(definition, workspace, adapter))
    result = service.execute(RunRequest(
        arguments.etl, arguments.fecha,
        inputs={"base": arguments.base, **dict(arguments.inputs)},
        params=dict(arguments.params),
    ))
    print(f"run={result.run_id} status={result.status.value}")
    if result.status is RunStatus.SUCCEEDED:
        return 0
    return 2 if result.status is RunStatus.BLOCKED else 1


if __name__ == "__main__":
    raise SystemExit(main())
