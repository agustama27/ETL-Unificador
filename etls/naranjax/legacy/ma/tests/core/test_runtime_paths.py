from __future__ import annotations

from core.runtime_paths import DEFAULT_DEV_PERSISTENCE_DIR, resolve_estado_dir, resolve_output_dir


def test_resolve_paths_return_none_when_no_overrides(monkeypatch) -> None:
    monkeypatch.delenv("NARANJAX_ESTADO_DIR", raising=False)
    monkeypatch.delenv("NARANJAX_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("NARANJAX_RUNTIME_BASE_DIR", raising=False)
    monkeypatch.delenv("NARANJAX_DEV_OUTPUT_DIR", raising=False)

    assert resolve_estado_dir(None) is None
    assert resolve_output_dir(None) is None


def test_resolve_paths_use_configured_dirs_before_default(monkeypatch) -> None:
    monkeypatch.delenv("NARANJAX_ESTADO_DIR", raising=False)
    monkeypatch.delenv("NARANJAX_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("NARANJAX_RUNTIME_BASE_DIR", raising=False)
    monkeypatch.delenv("NARANJAX_DEV_OUTPUT_DIR", raising=False)

    estado = resolve_estado_dir("C:/OneDrive/estado")
    output = resolve_output_dir("C:/OneDrive/salida")

    assert str(estado).replace("\\", "/") == "C:/OneDrive/estado"
    assert str(output).replace("\\", "/") == "C:/OneDrive/salida"


def test_resolve_paths_use_specific_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("NARANJAX_ESTADO_DIR", "C:/data/estado_env")
    monkeypatch.setenv("NARANJAX_OUTPUT_DIR", "C:/data/salida_env")

    estado = resolve_estado_dir("C:/OneDrive/estado")
    output = resolve_output_dir("C:/OneDrive/salida")

    assert str(estado).replace("\\", "/") == "C:/data/estado_env"
    assert str(output).replace("\\", "/") == "C:/data/salida_env"


def test_resolve_paths_use_shared_base_env_when_specific_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("NARANJAX_ESTADO_DIR", raising=False)
    monkeypatch.delenv("NARANJAX_OUTPUT_DIR", raising=False)
    monkeypatch.setenv("NARANJAX_RUNTIME_BASE_DIR", "C:/data/runtime")

    estado = resolve_estado_dir("C:/OneDrive/estado")
    output = resolve_output_dir("C:/OneDrive/salida")

    assert str(estado).replace("\\", "/") == "C:/data/runtime"
    assert str(output).replace("\\", "/") == "C:/data/runtime"


def test_resolve_paths_prioritize_explicit_over_env_and_default(monkeypatch) -> None:
    monkeypatch.setenv("NARANJAX_ESTADO_DIR", "C:/data/estado_env")
    monkeypatch.setenv("NARANJAX_OUTPUT_DIR", "C:/data/salida_env")

    estado = resolve_estado_dir("C:/OneDrive/estado", explicit_estado_dir="C:/manual/estado")
    output = resolve_output_dir("C:/OneDrive/salida", explicit_output_dir="C:/manual/salida")

    assert str(estado).replace("\\", "/") == "C:/manual/estado"
    assert str(output).replace("\\", "/") == "C:/manual/salida"
