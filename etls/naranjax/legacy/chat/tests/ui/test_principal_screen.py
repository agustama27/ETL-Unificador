from __future__ import annotations

from typing import Any, cast
from pathlib import Path
from queue import Queue
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.modelos import ConfigDia
from ui.screens.principal import PrincipalScreen, can_enable_process, collect_blocking_errors, empty_picker_status


def test_can_enable_process_requires_estado_ok() -> None:
    paths = {
        "base": Path("base.xlsx"),
        "planes": Path("planes.csv"),
        "pagos": None,
    }
    issues = {
        "base": [],
        "planes": [],
        "pagos": [],
        "estado": ["No hay estado mensual"],
    }
    assert can_enable_process(cast(dict[str, Path | None], paths), issues) is False


def test_can_enable_process_when_files_and_estado_are_valid() -> None:
    paths = {
        "base": Path("base.xlsx"),
        "planes": Path("planes.csv"),
        "pagos": None,
    }
    issues = {
        "base": [],
        "planes": [],
        "pagos": [],
        "estado": [],
    }
    assert can_enable_process(cast(dict[str, Path | None], paths), issues) is True


def test_collect_blocking_errors_includes_estado() -> None:
    issues = {
        "base": ["base_error"],
        "planes": [],
        "pagos": [],
        "estado": ["estado_error"],
    }
    assert collect_blocking_errors(issues) == ["base_error", "estado_error"]


def test_empty_picker_status_marks_pagos_as_optional() -> None:
    assert empty_picker_status("pagos") == ("No cargado (opcional)", "gray")
    assert empty_picker_status("base") == ("-", "gray")


def test_drain_queue_done_event_invokes_result_callback() -> None:
    class _DummyProgress:
        def __init__(self) -> None:
            self._value = 0.0

        def set(self, value: float) -> None:
            self._value = value

        def get(self) -> float:
            return self._value

    class _DummyLog:
        def __init__(self) -> None:
            self.lines: list[str] = []

        def insert(self, _where: str, value: str) -> None:
            self.lines.append(value)

        def see(self, _where: str) -> None:
            return

    received: list[tuple[object, object]] = []
    q: Queue[tuple[str, object]] = Queue()
    q.put(("done", {"ok": True}))

    screen = PrincipalScreen.__new__(PrincipalScreen)
    screen._queue = q
    screen.progress = cast(Any, _DummyProgress())
    screen.log_view = cast(Any, _DummyLog())
    screen._on_result = lambda result, error: received.append((result, error))

    PrincipalScreen._drain_queue(screen)

    assert received == [({"ok": True}, None)]


def test_generate_initial_state_runs_core_and_revalidates(monkeypatch, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    def _fake_generate(estado_dir: Path, input_base: Path, mes: str) -> Path:
        calls["estado_dir"] = estado_dir
        calls["input_base"] = input_base
        calls["mes"] = mes
        return estado_dir / f"estado_{mes}.csv"

    monkeypatch.setattr("ui.screens.principal.generar_estado_inicial", _fake_generate)

    screen = PrincipalScreen.__new__(PrincipalScreen)
    screen._config = ConfigDia(
        estado_dir=tmp_path / "estado",
        output_dir=tmp_path / "salida",
        logs_dir=tmp_path / "logs",
        procesados_dir=tmp_path / "procesados",
    )
    screen._paths = {"base": tmp_path / "base.xlsx", "planes": None, "pagos": None}

    def _fake_run_validations() -> None:
        calls["validated"] = True

    screen._run_validations = _fake_run_validations

    class _DummyLog:
        def __init__(self) -> None:
            self.lines: list[str] = []

        def insert(self, _where: str, value: str) -> None:
            self.lines.append(value)

        def see(self, _where: str) -> None:
            return

    screen.log_view = cast(Any, _DummyLog())

    PrincipalScreen._generate_initial_state(screen)

    assert calls["estado_dir"] == tmp_path / "estado"
    assert calls["input_base"] == tmp_path / "base.xlsx"
    assert isinstance(calls["mes"], str)
    assert calls.get("validated") is True
    assert screen.log_view.lines


def test_start_processing_without_daily_files_invokes_worker_with_mode(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class _DummyButton:
        def __init__(self) -> None:
            self.state = "normal"

        def configure(self, **kwargs) -> None:
            if "state" in kwargs:
                self.state = str(kwargs["state"])

    class _DummyProgress:
        def __init__(self) -> None:
            self._value = 0.0

        def set(self, value: float) -> None:
            self._value = value

        def get(self) -> float:
            return self._value

    class _DummyLog:
        def __init__(self) -> None:
            self.lines: list[str] = []

        def insert(self, _where: str, value: str) -> None:
            self.lines.append(value)

        def see(self, _where: str) -> None:
            return

    class _FakeWorker:
        def __init__(self, config, archivos, queue) -> None:
            captured["config"] = config
            captured["archivos"] = archivos
            captured["queue"] = queue

        def start(self) -> None:
            captured["started"] = True

    monkeypatch.setattr("ui.screens.principal.WorkerThread", _FakeWorker)

    screen = PrincipalScreen.__new__(PrincipalScreen)
    screen._config = ConfigDia(
        estado_dir=tmp_path / "estado",
        output_dir=tmp_path / "salida",
        logs_dir=tmp_path / "logs",
        procesados_dir=tmp_path / "procesados",
    )
    screen._paths = {"base": tmp_path / "base.xlsx", "planes": None, "pagos": None}
    screen._pagos_selected_current_session = False
    screen._issues = {"base": [], "planes": [], "pagos": [], "estado": ["No hay estado mensual"]}
    screen.process_btn = cast(Any, _DummyButton())
    screen.process_start_month_btn = cast(Any, _DummyButton())
    screen.progress = cast(Any, _DummyProgress())
    screen.log_view = cast(Any, _DummyLog())
    screen.after = lambda *_args, **_kwargs: None

    PrincipalScreen._start_processing_without_daily_files(screen)

    assert captured.get("started") is True
    assert "archivos" in captured
    archivos = cast(Any, captured["archivos"])
    assert archivos.modo_sin_diarios is True
    assert archivos.planes is None
