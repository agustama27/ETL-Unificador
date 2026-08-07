from __future__ import annotations

import logging
import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
BACK_BASE_DIR = ROOT_DIR / "back-base"
if str(BACK_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BACK_BASE_DIR))

from back_base_etl.constants import OUTPUT_COLUMNS_ROMAN, OUTPUT_FILENAME_E1KIA, OUTPUT_FILENAME_ROMAN
from back_base_etl.constants import MAX_DYNAMIC_PLANS, get_plan_column_names
from back_base_etl.estado_persistente import cargar_estado, guardar_estado, inicializar_estado
from back_base_etl.filtros import DEFAULT_CAJONES_SCOPE, aplicar_filtros
from back_base_etl.io import iter_planes_chunks, load_input, load_pagos, save_output
from back_base_etl.planes_pivot import pivot_planes
from back_base_etl.transformers import build_e1kia_output, sort_roman_rows, transform
from back_base_etl.update_estado import update_estado

from .log_bridge import bind_log_callback
from .modelos import ArchivosDia, ConfigDia, ResultadoDia


LOGGER = logging.getLogger("core.procesar_dia")
DEFAULT_PLAN_COVERAGE_THRESHOLD = 0.01


def detectar_archivos_diarios(input_dir: Path) -> dict[str, Path | list[Path] | None]:
    detected: dict[str, Path | list[Path] | None] = {"planes": None, "pagos": None, "no_reconocidos": []}
    if not input_dir.exists():
        return detected

    for entry in sorted([entry for entry in input_dir.iterdir() if entry.is_file()]):
        name = entry.name.lower()
        if entry.suffix.lower() == ".xlsx" and ("planes" in name or "cartera" in name):
            detected["planes"] = entry
            continue
        if entry.suffix.lower() == ".csv" and ("pagos" in name or "avanzada" in name):
            detected["pagos"] = entry
            continue
        no_reconocidos = detected["no_reconocidos"]
        assert isinstance(no_reconocidos, list)
        no_reconocidos.append(entry)
    return detected


def copiar_a_destino_unico(origen: Path, destino_dir: Path) -> Path:
    destino_dir.mkdir(parents=True, exist_ok=True)
    base = origen.stem
    suffix = origen.suffix
    candidato = destino_dir / origen.name
    intento = 1
    while candidato.exists():
        candidato = destino_dir / f"{base}__{intento}{suffix}"
        intento += 1
    return Path(shutil.copy2(str(origen), str(candidato)))


def mover_insumos_procesados(archivos_usados: list[Path], procesados_dir: Path, fecha: str) -> list[Path]:
    moved: list[Path] = []
    destino_fecha = procesados_dir / fecha
    for origen in archivos_usados:
        if not origen.exists():
            LOGGER.warning("Used daily file not found for copy: %s", origen)
            continue
        moved.append(copiar_a_destino_unico(origen, destino_fecha))
    return moved


def _count_rows_with_real_plan_data(df: pd.DataFrame, plan_columns: list[str]) -> int:
    if df.empty or not plan_columns:
        return 0
    present_columns = [column for column in plan_columns if column in df.columns]
    if not present_columns:
        return 0
    normalized = (
        df[present_columns]
        .fillna("")
        .astype(str)
        .apply(lambda series: series.str.strip())
    )
    return int((normalized != "").any(axis=1).sum())


def _resolve_plan_coverage_threshold() -> float:
    raw_value = os.getenv("NARANJAX_PLANES_MIN_COVERAGE", "").strip()
    if not raw_value:
        return DEFAULT_PLAN_COVERAGE_THRESHOLD
    try:
        parsed = float(raw_value)
    except ValueError as exc:
        raise ValueError(
            "Invalid NARANJAX_PLANES_MIN_COVERAGE value. Expected number between 0 and 1."
        ) from exc
    if parsed < 0 or parsed > 1:
        raise ValueError("Invalid NARANJAX_PLANES_MIN_COVERAGE value. Expected number between 0 and 1.")
    return parsed


def _build_monto_deuda_vencida_actual_map(df_pagos: pd.DataFrame | None) -> pd.Series | None:
    if df_pagos is None or df_pagos.empty or "nroproducto" not in df_pagos.columns:
        return None

    pagos = df_pagos.copy()
    pagos["nroproducto"] = pagos["nroproducto"].fillna("").astype(str).str.strip()
    pagos = pagos[pagos["nroproducto"] != ""]
    if pagos.empty:
        return None

    def _clean_amount(series: pd.Series) -> pd.Series:
        raw = series.fillna("").astype(str).str.replace("$", "", regex=False).str.strip()
        both_separators = raw.str.contains(".", regex=False) & raw.str.contains(",", regex=False)
        normalized = raw.where(~both_separators, raw.str.replace(".", "", regex=False))
        normalized = normalized.str.replace(",", ".", regex=False)
        return pd.to_numeric(normalized, errors="coerce")

    dv_actual_raw = pagos.get("dv_actual", pd.Series("", index=pagos.index, dtype=object)).fillna("").astype(str).str.strip()
    deuda_vencida_raw = pagos.get("deuda_vencida", pd.Series("", index=pagos.index, dtype=object)).fillna("").astype(str).str.strip()

    dv_actual = _clean_amount(dv_actual_raw)
    deuda_vencida = _clean_amount(deuda_vencida_raw)
    pagos["monto_deuda_vencida_actual"] = dv_actual.where(dv_actual_raw != "", deuda_vencida)

    return pagos.groupby("nroproducto")["monto_deuda_vencida_actual"].last()


def procesar_dia(config: ConfigDia, archivos: ArchivosDia, log_cb: Callable[[str], None] | None = None) -> ResultadoDia:
    with bind_log_callback(log_cb):
        try:
            archivos_diarios_usados: list[Path] = []
            try:
                df_estado_vigente = cargar_estado(str(config.estado_dir), archivos.mes)
                LOGGER.info("Loaded persistent state for month %s rows=%s", archivos.mes, len(df_estado_vigente))
                if df_estado_vigente.empty:
                    LOGGER.warning(
                        "Persistent state for month %s is empty. ROMAN/E1KIA outputs will be empty until base contains rows with cajon=M90 and ecosistema=PURO.",
                        archivos.mes,
                    )
                    df_base = load_input(str(archivos.input_base))
                    LOGGER.info(
                        "Rebuilding empty persistent state from base rows=%s path=%s",
                        len(df_base),
                        archivos.input_base,
                    )
                    inicializar_estado(df_base, str(config.estado_dir), archivos.mes)
                    df_estado_vigente = cargar_estado(str(config.estado_dir), archivos.mes)
                    LOGGER.info(
                        "Rebuilt persistent state for month %s rows=%s",
                        archivos.mes,
                        len(df_estado_vigente),
                    )
            except FileNotFoundError:
                LOGGER.info("Persistent state not found for month %s, initializing from base", archivos.mes)
                df_base = load_input(str(archivos.input_base))
                LOGGER.info("Loaded base input rows=%s path=%s", len(df_base), archivos.input_base)
                inicializar_estado(df_base, str(config.estado_dir), archivos.mes)
                df_estado_vigente = cargar_estado(str(config.estado_dir), archivos.mes)
                LOGGER.info("Initialized state for month %s rows=%s", archivos.mes, len(df_estado_vigente))
                if len(df_base) > 0 and df_estado_vigente.empty:
                    LOGGER.warning(
                        "State initialization produced 0 rows from a non-empty base (rows=%s). Expected base rows with cajon=M90 and ecosistema=PURO in mapped input columns.",
                        len(df_base),
                    )

            detected = detectar_archivos_diarios(archivos.diarios_dir)
            planes_detected = detected["planes"] if isinstance(detected["planes"], Path) else None
            pagos_detected = detected["pagos"] if isinstance(detected["pagos"], Path) else None
            planes_path = archivos.planes
            pagos_path = archivos.pagos
            pagos_enabled = bool(archivos.usar_pagos) and not archivos.modo_sin_diarios
            if planes_path is None and archivos.autodetect_planes:
                planes_path = planes_detected
            if pagos_enabled and pagos_path is None and archivos.autodetect_pagos:
                pagos_path = pagos_detected
            if not pagos_enabled:
                if pagos_path is not None:
                    LOGGER.warning("PAGOS path provided but PAGOS is disabled by user/session. Ignoring path=%s", pagos_path)
                pagos_path = None
                LOGGER.info("PAGOS omitted by user; skipping")
            if archivos.modo_sin_diarios:
                LOGGER.warning(
                    "Running in month-start mode without daily files: PLANES/PAGOS will be ignored intentionally"
                )
                planes_path = None
                pagos_path = None
            LOGGER.info(
                "Detected daily files planes=%s pagos=%s selected_planes=%s selected_pagos=%s",
                detected["planes"],
                detected["pagos"],
                planes_path,
                pagos_path,
            )

            if detected["no_reconocidos"]:
                LOGGER.warning("Unrecognized daily files: %s", detected["no_reconocidos"])

            df_planes_pivot = None
            if planes_path:
                LOGGER.info("Loading PLANES file: %s", planes_path)
                df_planes_pivot = pivot_planes(iter_planes_chunks(str(planes_path)))
                LOGGER.info(
                    "Processed PLANES rows=%s products=%s max_plans=%s",
                    df_planes_pivot.attrs.get("input_plan_rows", 0),
                    len(df_planes_pivot),
                    df_planes_pivot.attrs.get("max_plans", 0),
                )
                archivos_diarios_usados.append(planes_path)
            else:
                LOGGER.warning("PLANES file not provided, state keeps monthly/deferred values")

            df_pagos = None
            if pagos_path:
                LOGGER.info("Loading PAGOS file: %s", pagos_path)
                df_pagos = load_pagos(str(pagos_path))
                archivos_diarios_usados.append(pagos_path)
            else:
                LOGGER.info("PAGOS file not provided")

            plan_columns = [] if df_planes_pivot is None else list(df_planes_pivot.attrs.get("plan_columns", []))
            if archivos.modo_sin_diarios and not plan_columns:
                plan_columns = get_plan_column_names(MAX_DYNAMIC_PLANS)
                LOGGER.info(
                    "Month-start without daily files: generating ROMAN with controlled empty plan columns=%s",
                    len(plan_columns),
                )

            df_estado_actualizado = update_estado(df_estado_vigente, df_planes_pivot, df_pagos=df_pagos, logger=LOGGER)
            df_roman, resumen_filtros = aplicar_filtros(df_estado_actualizado, scope_cajones=DEFAULT_CAJONES_SCOPE, logger=LOGGER)

            pagos_monto_map = _build_monto_deuda_vencida_actual_map(df_pagos)
            if pagos_monto_map is not None and not pagos_monto_map.empty and "nroproducto" in df_roman.columns:
                df_roman = df_roman.copy()
                df_roman["monto_deuda_vencida_actual"] = (
                    df_roman["nroproducto"].fillna("").astype(str).str.strip().map(pagos_monto_map)
                )

            output_df = transform(
                df_roman,
                plan_columns=plan_columns,
                output_columns_base=OUTPUT_COLUMNS_ROMAN,
                logger=LOGGER,
            )
            output_df = sort_roman_rows(output_df)

            if planes_path:
                plan_rows_estado = _count_rows_with_real_plan_data(df_estado_actualizado, plan_columns)
                plan_rows_scope = _count_rows_with_real_plan_data(df_roman, plan_columns)
                plan_rows_output = _count_rows_with_real_plan_data(output_df, plan_columns)
                min_coverage = _resolve_plan_coverage_threshold()
                output_rows = len(output_df)
                output_coverage = (plan_rows_output / output_rows) if output_rows > 0 else 0.0

                if plan_rows_estado == 0 and plan_rows_scope == 0:
                    LOGGER.info(
                        "PLANES diagnostics - no real plan data detected (estado=%s scope=%s output=%s)",
                        plan_rows_estado,
                        plan_rows_scope,
                        plan_rows_output,
                    )
                else:
                    LOGGER.info(
                        "PLANES diagnostics - rows with non-empty plan_* (estado=%s scope=%s output=%s)",
                        plan_rows_estado,
                        plan_rows_scope,
                        plan_rows_output,
                    )

                if len(output_df) > 0 and plan_rows_output == 0 and (plan_rows_scope > 0 or plan_rows_estado > 0):
                    raise ValueError(
                        "PLANES inconsistency detected: output ROMAN has all plan_* empty despite plan evidence in estado/scope"
                    )
                if output_rows > 0 and output_coverage < min_coverage:
                    raise ValueError(
                        "PLANES fail-fast: archivo PLANES presente, pero cobertura de plan_* en ROMAN "
                        f"es {output_coverage:.2%} (filas con plan={plan_rows_output}/{output_rows}), "
                        f"por debajo del minimo configurado {min_coverage:.2%}. "
                        "Revisar llave de cruce y formato del diario PLANES."
                    )

            output_path = Path(save_output(output_df, str(config.output_dir), prefix=OUTPUT_FILENAME_ROMAN))
            e1kia_df = build_e1kia_output(output_df)
            e1kia_path = Path(
                save_output(
                    e1kia_df,
                    str(config.output_dir),
                    prefix=OUTPUT_FILENAME_E1KIA,
                    date_format="%y%m%d",
                    suffix="_sinestrategia.csv",
                )
            )

            path_vigente, path_snapshot = guardar_estado(df_estado_actualizado, str(config.estado_dir), archivos.fecha)
            copied_files = mover_insumos_procesados(archivos_diarios_usados, config.procesados_dir, archivos.fecha)
            LOGGER.info(
                "Daily summary - mode=%s, input_rows=%s, estado_rows=%s, roman_rows=%s, excluidos_scope=%s, output_roman=%s, output_e1kia=%s, vigente=%s, snapshot=%s, copied_files=%s",
                "inicio_mes_sin_diarios" if archivos.modo_sin_diarios else "diario",
                len(df_estado_vigente),
                len(df_estado_actualizado),
                len(df_roman),
                resumen_filtros.get("cajon_fuera_scope", 0),
                output_path,
                e1kia_path,
                path_vigente,
                path_snapshot,
                [str(path) for path in copied_files],
            )

            return ResultadoDia(
                status="success",
                fecha=archivos.fecha,
                mes=archivos.mes,
                rows_estado_vigente=len(df_estado_vigente),
                rows_estado_actualizado=len(df_estado_actualizado),
                rows_roman=len(df_roman),
                exclusiones_por_motivo={"cajon_fuera_scope": int(resumen_filtros.get("cajon_fuera_scope", 0))},
                output_roman=output_path,
                output_e1kia=e1kia_path,
                estado_vigente_path=Path(path_vigente),
                estado_snapshot_path=Path(path_snapshot),
                archivos_movidos=copied_files,
                modo_ejecucion="inicio_mes_sin_diarios" if archivos.modo_sin_diarios else "diario",
                errores=[],
            )
        except Exception as exc:
            LOGGER.exception("Daily execution failed in core")
            return ResultadoDia(status="error", fecha=archivos.fecha, mes=archivos.mes, errores=[str(exc)])
