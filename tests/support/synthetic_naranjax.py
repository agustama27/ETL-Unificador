from pathlib import Path


OUTPUTS = {
    "chat": ("NARANJAX_MA_ROMAN_20260721.csv", "NARANJAX_MA_CHAT_ROMAN_260721.csv",
             "NARANJAX_MA_E1KIA_260721_sinestrategia.csv"),
    "voice": ("NARANJAX_MA_ROMAN_20260721.csv",
              "NARANJAX_MA_E1KIA_260721_sinestrategia.csv"),
    "pct": ("NARANJAX_PCT_20260721.csv",),
    "mt": ("NARANJAX_MT_ROMAN_260721.csv", "NARANJAX_MT_E1KIA_260721.csv"),
    "mt_pct": ("DEELO_NAR_USUEVOLTIS_20260721.txt",),
    "back": ("DEELO_NAR_USUEVOLTIS_20260721_15.txt", "_anomalias_20260721_153000.txt"),
    "encuestacx": ("base_encuesta.csv", "base_encuesta_e164.csv"),
}

AMBIGUOUS = {
    "chat": "NARANJAX_MA_CHAT_ROMAN_copy_260721.csv",
    "voice": "NARANJAX_MA_ROMAN_copy_260721.csv",
    "pct": "NARANJAX_PCT_copy_20260721.csv",
    "mt": "NARANJAX_MT_ROMAN_copy_260721.csv",
    "mt_pct": "DEELO_NAR_USUEVOLTIS_copy_20260721.txt",
    "back": "DEELO_NAR_USUEVOLTIS_copy_20260721_15.txt",
}


def write_result(run: Path, mode: str = "success", *, channel: str = "chat") -> None:
    names = list(OUTPUTS[channel])
    if mode == "missing":
        names.pop()
    elif mode == "ambiguous":
        names.append(AMBIGUOUS[channel])
    for name in names:
        (run / "output" / name).write_text("synthetic", encoding="utf-8")
    if channel in {"chat", "voice"}:
        (run / "state" / "estado_202607.csv").write_text("state", encoding="utf-8")
