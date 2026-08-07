from __future__ import annotations

import naranjax_etl


def test_main_dispatches_cli_without_ui_import(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["naranjax_etl.py", "--cli", "--base", "a", "--planes", "b"])

    captured: dict[str, list[str] | None] = {"argv": None}

    def _fake_run_cli(argv):
        captured["argv"] = argv
        return 7

    monkeypatch.setattr("cli.main.run_cli", _fake_run_cli)
    result = naranjax_etl.main()
    assert result == 7
    assert captured["argv"] is not None
    assert "--cli" not in captured["argv"]
