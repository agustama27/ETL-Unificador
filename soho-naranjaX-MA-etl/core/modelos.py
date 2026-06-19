from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ConfigDia:
    estado_dir: Path
    output_dir: Path
    logs_dir: Path
    procesados_dir: Path


@dataclass(frozen=True)
class ArchivosDia:
    fecha: str
    mes: str
    input_base: Path
    diarios_dir: Path
    planes: Path | None = None
    pagos: Path | None = None
    usar_pagos: bool = False
    autodetect_planes: bool = True
    autodetect_pagos: bool = True
    modo_sin_diarios: bool = False


@dataclass(frozen=True)
class ResultadoDia:
    status: str
    fecha: str
    mes: str
    rows_estado_vigente: int = 0
    rows_estado_actualizado: int = 0
    rows_roman: int = 0
    exclusiones_por_motivo: dict[str, int] = field(default_factory=dict)
    output_roman: Path | None = None
    output_e1kia: Path | None = None
    output_pct: Path | None = None
    estado_vigente_path: Path | None = None
    estado_snapshot_path: Path | None = None
    archivos_movidos: list[Path] = field(default_factory=list)
    log_file: Path | None = None
    modo_ejecucion: str = "diario"
    errores: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ConfigTipificaciones:
    output_dir: Path
    cruce_origen: str = "none"
    cruce_path: Path | None = None
    cruce_lookup_path: Path | None = None


@dataclass(frozen=True)
class ResultadoTipificaciones:
    status: str
    total_input_rows: int = 0
    total_output_rows: int = 0
    omitted_rows_total: int = 0
    omitted_by_reason: dict[str, int] = field(default_factory=dict)
    warning_count: int = 0
    output_path: Path | None = None
    output_contract: dict[str, str | int] = field(default_factory=dict)
    errores: list[str] = field(default_factory=list)
