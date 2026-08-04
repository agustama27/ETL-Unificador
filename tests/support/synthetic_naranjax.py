from pathlib import Path


OUTPUTS = {
    "chat": ("NARANJAX_MA_ROMAN_20260721.csv", "NARANJAX_MA_CHAT_ROMAN_260721.csv",
             "NARANJAX_MA_E1KIA_260721_sinestrategia.csv"),
    "voice": ("NARANJAX_MA_ROMAN_20260721.csv",
              "NARANJAX_MA_E1KIA_260721_sinestrategia.csv"),
}


def write_result(run: Path, mode: str = "success", *, channel: str = "chat") -> None:
    names = list(OUTPUTS[channel])
    if mode == "missing":
        names.pop()
    elif mode == "ambiguous":
        names.append(f"NARANJAX_MA_{'CHAT_ROMAN_copy_' if channel == 'chat' else 'ROMAN_copy_'}260721.csv")
    for name in names:
        (run / "output" / name).write_text("synthetic", encoding="utf-8")
    (run / "state" / "estado_202607.csv").write_text("state", encoding="utf-8")
