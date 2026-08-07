from __future__ import annotations

from typing import Any, cast
from pathlib import Path
from queue import Queue
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.modelos import ConfigDia
from ui.screens.principal import (
    PrincipalScreen,
    can_enable_process,
    collect_blocking_errors,
    empty_picker_status,
    format_back_error_message,
    format_omitted_by_reason,
    selected_file_status,
)


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


def test_selected_file_status_reports_name_and_parent(tmp_path: Path) -> None:
    target = tmp_path / "archivo.csv"
    target.write_text("ok", encoding="utf-8")

    text, color = selected_file_status(str(target))

    assert color == "green"
    assert target.name in text
    assert str(target.parent) in text


def test_selected_file_status_returns_dash_for_missing_or_empty_path() -> None:
    assert selected_file_status("") == ("-", "gray")
    assert selected_file_status("C:/ruta/inexistente/no.csv") == ("-", "gray")


def test_format_omitted_by_reason_render_human_readable_text() -> None:
    assert format_omitted_by_reason({}) == "-"
    assert format_omitted_by_reason({"missing_dni": 1, "unmapped_tipificacion": 2}) == "missing_dni: 1, unmapped_tipificacion: 2"


def test_format_back_error_message_maps_common_cases() -> None:
    assert "No hay input disponible" in format_back_error_message("No input file selected and no files found in default folder 'x'")
    assert "columnas requeridas" in format_back_error_message("Missing required source columns: call_id")
    assert format_back_error_message("Error desconocido") == "Error desconocido"


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
    cast(Any, screen).after = lambda *_args, **_kwargs: "after-id"

    PrincipalScreen._start_processing_without_daily_files(screen)

    assert captured.get("started") is True
    assert "archivos" in captured
    archivos = cast(Any, captured["archivos"])
    assert archivos.modo_sin_diarios is True
    assert archivos.planes is None


def test_show_module_switches_between_daily_and_back_resultados() -> None:
    class _DummyFrame:
        def __init__(self) -> None:
            self.pack_calls = 0
            self.pack_forget_calls = 0

        def pack(self, **_kwargs) -> None:
            self.pack_calls += 1

        def pack_forget(self) -> None:
            self.pack_forget_calls += 1

    screen = PrincipalScreen.__new__(PrincipalScreen)
    screen._daily_frame = cast(Any, _DummyFrame())
    screen._back_resultados_frame = cast(Any, _DummyFrame())

    PrincipalScreen._show_module(screen, "Back Resultados")
    assert screen._daily_frame.pack_forget_calls == 1
    assert screen._back_resultados_frame.pack_calls == 1

    PrincipalScreen._show_module(screen, "Ejecucion diaria")
    assert screen._back_resultados_frame.pack_forget_calls == 1
    assert screen._daily_frame.pack_calls == 1


def test_start_back_resultados_requires_file_in_file_mode(monkeypatch) -> None:
    errors: list[str] = []
    monkeypatch.setattr("ui.screens.principal.messagebox.showerror", lambda _title, message: errors.append(message))

    screen = PrincipalScreen.__new__(PrincipalScreen)
    screen._back_input_mode = cast(Any, type("_V", (), {"get": lambda self: "file"})())
    screen._back_input_file = cast(Any, type("_V", (), {"get": lambda self: ""})())
    screen._back_cruce_mode = cast(Any, type("_V", (), {"get": lambda self: "logcall"})())
    screen._back_cruce_file = cast(Any, type("_V", (), {"get": lambda self: ""})())
    screen._back_lookup_file = cast(Any, type("_V", (), {"get": lambda self: ""})())
    screen._back_output_dir = cast(Any, type("_V", (), {"get": lambda self: "C:/tmp/out"})())

    PrincipalScreen._start_back_resultados_processing(screen)

    assert errors
    assert "Selecciona un archivo" in errors[0]


def test_start_back_resultados_starts_worker(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Var:
        def __init__(self, value: str) -> None:
            self.value = value

        def get(self) -> str:
            return self.value

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

    class _DummyLabel:
        def configure(self, **_kwargs) -> None:
            return

    class _DummyLog:
        def insert(self, _where: str, _value: str) -> None:
            return

        def see(self, _where: str) -> None:
            return

    class _FakeWorker:
        def __init__(
            self,
            selected_input,
            output_dir,
            queue,
            cruce_origen="none",
            cruce_path=None,
            cruce_lookup_path=None,
        ) -> None:
            captured["selected_input"] = selected_input
            captured["output_dir"] = output_dir
            captured["queue"] = queue
            captured["cruce_origen"] = cruce_origen
            captured["cruce_path"] = cruce_path
            captured["cruce_lookup_path"] = cruce_lookup_path

        def start(self) -> None:
            captured["started"] = True

    monkeypatch.setattr("ui.screens.principal.BackResultadosWorkerThread", _FakeWorker)
    monkeypatch.setattr("ui.screens.principal.load_config", lambda: {})
    monkeypatch.setattr("ui.screens.principal.save_config", lambda _cfg: None)

    screen = PrincipalScreen.__new__(PrincipalScreen)
    cast(Any, screen)._back_input_mode = _Var("roman")
    cast(Any, screen)._back_input_file = _Var("")
    cast(Any, screen)._back_cruce_mode = _Var("logcall")
    cast(Any, screen)._back_cruce_file = _Var("C:/tmp/logcall.csv")
    cast(Any, screen)._back_lookup_file = _Var("C:/tmp/lookup.csv")
    cast(Any, screen)._back_output_dir = _Var("C:/tmp/out")
    screen.back_process_btn = cast(Any, _DummyButton())
    screen._back_open_output_btn = cast(Any, _DummyButton())
    screen.back_progress = cast(Any, _DummyProgress())
    screen._back_status_label = cast(Any, _DummyLabel())
    screen._back_metrics_label = cast(Any, _DummyLabel())
    screen.back_log_view = cast(Any, _DummyLog())
    cast(Any, screen).after = lambda *_args, **_kwargs: "after-id"

    PrincipalScreen._start_back_resultados_processing(screen)

    assert captured.get("started") is True
    assert captured.get("selected_input") is None
    assert captured.get("output_dir") == "C:/tmp/out"
    assert captured.get("cruce_origen") == "logcall"
    assert captured.get("cruce_lookup_path") == "C:/tmp/lookup.csv"


def test_drain_queue_back_resultados_done_populates_metrics_and_contract() -> None:
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

    class _DummyLabel:
        def __init__(self) -> None:
            self.text = ""

        def configure(self, **kwargs) -> None:
            if "text" in kwargs:
                self.text = str(kwargs["text"])

    class _DummyButton:
        def __init__(self) -> None:
            self.state = "disabled"

        def configure(self, **kwargs) -> None:
            if "state" in kwargs:
                self.state = str(kwargs["state"])

    q: Queue[tuple[str, object]] = Queue()
    q.put(
        (
            "done",
            type(
                "_R",
                (),
                {
                    "status": "success",
                    "total_input_rows": 12,
                    "total_output_rows": 10,
                    "omitted_rows_total": 2,
                    "omitted_by_reason": {"missing_dni": 1, "unmapped_tipificacion": 1},
                    "warning_count": 2,
                    "output_path": Path("C:/tmp/out/NARANJAX_PCT_20260505.csv"),
                    "output_contract": {"delimiter": "|", "encoding": "cp1252", "columns": 7, "date_format": "yyyyMMdd"},
                },
            )(),
        )
    )

    screen = PrincipalScreen.__new__(PrincipalScreen)
    screen._queue = q
    screen._active_run = "back_resultados"
    screen.back_progress = cast(Any, _DummyProgress())
    screen.back_process_btn = cast(Any, _DummyButton())
    screen._back_open_output_btn = cast(Any, _DummyButton())
    screen._back_status_label = cast(Any, _DummyLabel())
    screen._back_metrics_label = cast(Any, _DummyLabel())
    screen._back_contract_label = cast(Any, _DummyLabel())
    screen.back_log_view = cast(Any, _DummyLog())

    PrincipalScreen._drain_queue(screen)

    assert "input=12" in screen._back_metrics_label.text
    assert "missing_dni: 1" in screen._back_metrics_label.text
    assert "cp1252" in screen._back_contract_label.text
    assert screen._back_open_output_btn.state == "normal"
