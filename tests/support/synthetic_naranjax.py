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
    "bancor": ("con-filtros/base_bancor_21072026.csv",
               "con-filtros/telefonos_x_cliente_21072026.csv",
               "sin-filtros/BANCOR_ROMAN_20260721.csv",
               "sin-filtros/BANCOR_E1KIA_20260721_sinestrategia.csv"),
    "epec": ("EPEC_ROMAN_260721.csv", "EPEC_E1KIA_260721.csv"),
    "fravega": ("fravega_base.csv",),
    "clarouy": ("base_clarouy_21072026.csv", "telefonos_x_cliente_21072026.csv"),
    "social_arg": ("SOCIAL_ARG_CARTERA_20260721.csv",),
    "social_chi": ("SOCIAL_CHI_CARTERA_20260721.csv",),
    "petersen": ("Gestiones_Petersen_20260721.zip",),
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
        target = run / "output" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("synthetic", encoding="utf-8")
    if channel in {"chat", "voice"}:
        (run / "state" / "estado_202607.csv").write_text("state", encoding="utf-8")
