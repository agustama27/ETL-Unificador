from __future__ import annotations

from pathlib import Path

from core.estado_inicial import generar_estado_inicial


def test_generar_estado_inicial_creates_expected_monthly_state(monkeypatch, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    def _fake_load_input(path: str):
        calls["base_path"] = path
        return object()

    def _fake_inicializar_estado(df_base, output_dir: str, mes: str) -> str:
        calls["df_base"] = df_base
        calls["output_dir"] = output_dir
        calls["mes"] = mes
        return str(Path(output_dir) / f"estado_{mes}.csv")

    monkeypatch.setattr("core.estado_inicial.load_input", _fake_load_input)
    monkeypatch.setattr("core.estado_inicial.inicializar_estado", _fake_inicializar_estado)

    estado_dir = tmp_path / "estado"
    base = tmp_path / "base.xlsx"
    result = generar_estado_inicial(estado_dir=estado_dir, input_base=base, mes="202604")

    assert result == estado_dir / "estado_202604.csv"
    assert calls["base_path"] == str(base)
    assert calls["output_dir"] == str(estado_dir)
    assert calls["mes"] == "202604"
