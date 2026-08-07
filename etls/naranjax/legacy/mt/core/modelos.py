from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConfigDia:
    estado_dir: Path
    output_dir: Path
    logs_dir: Path
    procesados_dir: Path


@dataclass
class ArchivosDia:
    base_entrada: Path | None = None
    usar_base_reciente: bool = True


@dataclass
class ResultadoDia:
    status: str
    output_base: Path | None = None
    output_telefonos: Path | None = None
    rows_entrada: int = 0
    rows_salida: int = 0
    exclusiones_por_motivo: dict[str, int] = field(default_factory=dict)
    errores: list[str] = field(default_factory=list)
    modo_ejecucion: str = "ui"


@dataclass
class ConfigTipificaciones:
    output_dir: Path
    cruce_origen: str = "none"
    cruce_path: Path | None = None
    cruce_lookup_path: Path | None = None


@dataclass
class ResultadoTipificaciones:
    status: str
    total_input_rows: int = 0
    total_output_rows: int = 0
    omitted_rows_total: int = 0
    omitted_by_reason: dict[str, int] = field(default_factory=dict)
    warning_count: int = 0
    output_path: Path | None = None
    output_contract: dict = field(default_factory=dict)
    errores: list[str] = field(default_factory=list)
