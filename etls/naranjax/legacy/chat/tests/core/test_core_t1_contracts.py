from __future__ import annotations

import logging
import sys
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.log_bridge import bind_log_callback
from core.modelos import ArchivosDia, ConfigDia

procesar_dia_module = importlib.import_module("core.procesar_dia")


def test_log_bridge_callback_receives_lines_in_order() -> None:
    received: list[str] = []
    logger = logging.getLogger("test.synthetic.bridge")
    logger.setLevel(logging.INFO)

    with bind_log_callback(received.append):
        logger.info("linea uno")
        assert len(received) == 1
        logger.warning("linea dos")
        assert len(received) == 2

    assert "linea uno" in received[0]
    assert "linea dos" in received[1]


def test_procesar_dia_returns_structured_error_without_sys_exit(monkeypatch) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("forced-core-error")

    monkeypatch.setattr(procesar_dia_module, "load_input", _boom)

    config = ConfigDia(
        estado_dir=Path("C:/tmp/estado"),
        output_dir=Path("C:/tmp/output"),
        logs_dir=Path("C:/tmp/logs"),
        procesados_dir=Path("C:/tmp/procesados"),
    )
    archivos = ArchivosDia(
        fecha="20260430",
        mes="202604",
        input_base=Path("C:/tmp/base.xlsx"),
        diarios_dir=Path("C:/tmp/diarios"),
    )

    resultado = procesar_dia_module.procesar_dia(config=config, archivos=archivos, log_cb=None)

    assert resultado.status == "error"
    assert resultado.errores
    assert "forced-core-error" in resultado.errores[0]
