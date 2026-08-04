from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest

from orchestrator.models import (
    ArtifactRole,
    ETLDefinition,
    FileEvidence,
    InputSpec,
    OutputSpec,
    ProcessResult,
    Readiness,
    RepositoryStatus,
    RunRequest,
    RunResult,
    RunStatus,
    StateEffect,
    StateStatus,
)


def test_status_and_role_enums_expose_stable_string_values() -> None:
    assert [item.value for item in RepositoryStatus] == ["present"]
    assert [item.value for item in Readiness] == ["candidate", "blocked", "ready"]
    assert [item.value for item in RunStatus] == [
        "preparing", "running", "succeeded", "failed", "timed_out", "blocked"
    ]
    assert [item.value for item in StateStatus] == [
        "not_started", "staged", "promoted", "recovery_required"
    ]
    assert [item.value for item in ArtifactRole] == [
        "roman", "chat", "e1kia", "pct", "anomalies", "survey_base",
        "survey_base_e164", "base_filtrada", "telefonos", "legacy_log"
    ]


def test_run_request_defensively_freezes_extras(tmp_path: Path) -> None:
    extras = {"logcall": tmp_path / "logcall.csv"}
    request = RunRequest("etl", date(2026, 7, 21), tmp_path / "base.txt", extras=extras)

    extras["historial"] = tmp_path / "historial.csv"

    assert dict(request.extras) == {"logcall": tmp_path / "logcall.csv"}
    with pytest.raises(TypeError):
        request.extras["other"] = tmp_path / "other.csv"  # type: ignore[index]
    assert RunRequest("etl", date(2026, 7, 21), tmp_path / "base.txt").extras == {}


def test_etl_definition_is_frozen_and_defensively_freezes_arguments() -> None:
    arguments = {"business_date": "--fecha"}
    definition = ETLDefinition(
        id="naranjax.ma.chat.daily",
        name="Naranja X MA Chat daily",
        repository_status=RepositoryStatus.PRESENT,
        readiness=Readiness.CANDIDATE,
        executable=False,
        project_path=Path("SOHO-Chat-NX_MA-ETL"),
        arguments=arguments,
        inputs=(InputSpec("base", (".xlsx",), True),),
        outputs=(OutputSpec(ArtifactRole.CHAT, "CHAT_*.csv", "YYMMDD"),),
    )

    arguments["business_date"] = "--changed"
    assert definition.arguments == {"business_date": "--fecha"}
    assert definition.project_path == Path("SOHO-Chat-NX_MA-ETL")
    with pytest.raises(TypeError):
        definition.arguments["new"] = "--new"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        definition.executable = True  # type: ignore[misc]


def test_request_defensively_freezes_environment() -> None:
    environment = {"SAFE_SETTING": "enabled"}
    request = RunRequest(
        "naranjax.ma.chat.daily",
        date(2026, 7, 21),
        Path("input/base.xlsx"),
        environment=environment,
    )

    environment["SAFE_SETTING"] = "changed"
    assert request.environment == {"SAFE_SETTING": "enabled"}
    with pytest.raises(TypeError):
        request.environment["OTHER"] = "value"  # type: ignore[index]


def test_result_contract_composes_typed_process_file_and_state_evidence() -> None:
    artifact = FileEvidence("chat", Path("output/chat.csv"), 12, 34, "abc123")
    process = ProcessResult(0, False, ("started", "finished"))
    result = RunResult(
        "run-1",
        RunStatus.SUCCEEDED,
        None,
        (artifact,),
        StateEffect("202607", StateStatus.PROMOTED),
    )

    assert process == ProcessResult(0, False, ("started", "finished"))
    assert result.artifacts == (artifact,)
    assert result.state == StateEffect("202607", StateStatus.PROMOTED)
