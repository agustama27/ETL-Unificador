"""Configuración de ejecución del pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Mapping


SOURCE_METADATA = {
    "saldos": ("saldos.xls", (".xls", ".csv")),
    "maquinarias": ("maquinarias.xlsx", ".xlsx"),
    "repuestos": ("repuestos.pdf", ".pdf"),
    "servicios": ("servicios.xlsx", ".xlsx"),
}

# Autologica no exporta con nombres estables ("saldos Agosto.csv",
# "REMITOS - REPUESTOS (4).pdf"), asi que exigir el nombre canonico obliga al
# operador a renombrar cuatro archivos por dia. Cuando el nombre canonico no
# esta en la particion, cada fuente se identifica por su extension: saldos es
# el unico .csv/.xls y repuestos el unico .pdf. Los dos .xlsx son la unica
# ambiguedad real y se desempatan por esta marca en el nombre.
_MARCA_SERVICIOS = "servicio"
_SUFIJOS_SALDOS = (".csv", ".xls")
_SUFIJO_REPUESTOS = ".pdf"
_SUFIJO_REMITOS_XLSX = ".xlsx"

# Naming pedido por cada consumidor: <PREFIJO>_YYMMDD.csv, con la fecha de
# la partición de la corrida (`run_date`), no la fecha de cálculo.
ROMAN_EXPORT_PREFIX = "ALVAREZ_MAQUINARIAS_ROMAN"
APPROACH_EXPORT_PREFIX = "ALVAREZ_MAQUINARIAS_E1KIA"


@dataclass(frozen=True)
class PipelineConfig:
    """Parámetros de una corrida del ETL.

    La fecha de referencia se pide explícita para que cada corrida sea
    reproducible.
    """

    saldos_generales_path: Path
    maquinarias_path: Path
    remitos_repuestos_path: Path
    remitos_servicios_path: Path
    output_dir: Path
    reference_date: date = field(default_factory=date.today)
    run_date: date = field(default_factory=date.today)
    overwrite: bool = False
    telefono_min_digitos: int = 8
    telefono_max_digitos: int = 13

    @property
    def roman_output_path(self) -> Path:
        return self.output_dir / f"{ROMAN_EXPORT_PREFIX}_{self.run_date:%y%m%d}.csv"

    @property
    def approach_output_path(self) -> Path:
        return self.output_dir / f"{APPROACH_EXPORT_PREFIX}_{self.run_date:%y%m%d}.csv"

    @classmethod
    def for_dated_run(
        cls,
        project_root: Path,
        source_names: Mapping[str, str],
        reference_date: date,
        overwrite: bool,
        run_date: date | None = None,
        input_date: date | None = None,
        output_date: date | None = None,
    ) -> "PipelineConfig":
        if run_date is not None and (input_date is not None or output_date is not None):
            raise ValueError("usar run_date o input_date/output_date, no ambos")
        if (input_date is None) != (output_date is None):
            raise ValueError("input_date y output_date deben indicarse juntos")
        input_date = input_date or run_date
        output_date = output_date or run_date
        if input_date is None or output_date is None:
            raise ValueError("se requiere una fecha de input y output")
        root = project_root.resolve()
        input_dir = (root / "inputs" / input_date.isoformat()).resolve()
        if not input_dir.is_dir():
            raise ValueError(
                f"No existe la partición de entrada inputs/{input_date.isoformat()}/. "
                f"Crearla con: python main.py --preparar --run-date {input_date.isoformat()}"
            )
        source_paths, errors = cls._resolve_sources(
            input_dir, _resolve_source_names(input_dir, source_names)
        )
        if errors:
            raise ValueError(
                "Entradas inválidas: " + "; ".join(errors) + _detalle_particion(input_dir)
            )
        return cls(
            saldos_generales_path=source_paths["saldos"],
            maquinarias_path=source_paths["maquinarias"],
            remitos_repuestos_path=source_paths["repuestos"],
            remitos_servicios_path=source_paths["servicios"],
            output_dir=root / "outputs" / output_date.isoformat(),
            reference_date=reference_date,
            run_date=output_date,
            overwrite=overwrite,
        )

    @staticmethod
    def _resolve_sources(
        input_dir: Path, source_names: Mapping[str, str | None]
    ) -> tuple[dict[str, Path], list[str]]:
        source_paths: dict[str, Path] = {}
        errors: list[str] = []
        for role, (default_name, allowed_suffixes) in SOURCE_METADATA.items():
            filename = source_names.get(role, default_name)
            if filename is None:
                errors.append(
                    f"{role}: no se pudo identificar un único archivo por su extensión"
                )
                continue
            path = Path(filename)
            if not _is_valid_source_name(path, allowed_suffixes):
                errors.append(f"{role}: nombre de archivo inválido")
                continue

            candidate = (input_dir / path).resolve()
            try:
                candidate.relative_to(input_dir)
            except ValueError:
                errors.append(f"{role}: ruta fuera de la partición de entrada")
                continue
            if not candidate.is_file():
                errors.append(f"{role}: archivo faltante o no regular")
                continue
            if not _is_readable(candidate):
                errors.append(f"{role}: archivo no legible")
                continue
            source_paths[role] = candidate
        return source_paths, errors


def _resolve_source_names(
    input_dir: Path, source_names: Mapping[str, str]
) -> dict[str, str | None]:
    """Nombre de archivo efectivo de cada fuente, en tres niveles:

    1. el que indicó el operador (`--saldos X`): manda siempre, y si no está
       la corrida aborta — pidió un archivo puntual, no una sugerencia;
    2. el nombre canónico (`saldos.xls`…), si está presente en la partición;
    3. descubrimiento por extensión, para los exports que llegan con el
       nombre que les puso Autologica.

    El descubrimiento solo **propone** un nombre. La validación —extensión
    admitida, basename seguro, contención dentro de la partición,
    legibilidad— la sigue haciendo `_resolve_sources`, que es el único
    límite de confianza del módulo y no se toca.
    """
    resueltos: dict[str, str | None] = {}
    descubiertos: dict[str, str] | None = None
    for role, (default_name, _) in SOURCE_METADATA.items():
        elegido = source_names.get(role, default_name)
        if elegido != default_name or (input_dir / default_name).is_file():
            resueltos[role] = elegido
            continue
        if descubiertos is None:
            descubiertos = _discover_source_names(input_dir)
        # None cuando el descubrimiento no resolvió a un único archivo: se
        # distingue de "el archivo no está" para que el error sea honesto.
        resueltos[role] = descubiertos.get(role)
    return resueltos


def _discover_source_names(input_dir: Path) -> dict[str, str]:
    """Asigna los archivos de la partición a cada fuente por su extensión.

    Se deduce de la forma, nunca se adivina: si una regla no resuelve a
    exactamente un archivo, esa fuente queda sin asignar y la corrida aborta
    nombrando lo que sí había. Mismo criterio que el resto del ETL —
    preferimos un fallo ruidoso a una fuente elegida al azar.
    """
    por_sufijo: dict[str, list[str]] = {}
    try:
        entradas = sorted(input_dir.iterdir())
    except OSError:
        return {}
    for entrada in entradas:
        if entrada.is_file():
            por_sufijo.setdefault(entrada.suffix.lower(), []).append(entrada.name)

    hallados: dict[str, str] = {}
    saldos = [n for sufijo in _SUFIJOS_SALDOS for n in por_sufijo.get(sufijo, [])]
    if len(saldos) == 1:
        hallados["saldos"] = saldos[0]
    repuestos = por_sufijo.get(_SUFIJO_REPUESTOS, [])
    if len(repuestos) == 1:
        hallados["repuestos"] = repuestos[0]

    # Maquinarias y servicios comparten extensión: solo se identifica
    # positivamente a servicios, y el .xlsx restante es maquinarias.
    xlsx = por_sufijo.get(_SUFIJO_REMITOS_XLSX, [])
    servicios = [n for n in xlsx if _MARCA_SERVICIOS in n.lower()]
    maquinarias = [n for n in xlsx if n not in servicios]
    if len(servicios) == 1:
        hallados["servicios"] = servicios[0]
    if len(maquinarias) == 1:
        hallados["maquinarias"] = maquinarias[0]
    return hallados


def _detalle_particion(input_dir: Path) -> str:
    """Lista los archivos presentes para que el error sea accionable."""
    try:
        presentes = sorted(p.name for p in input_dir.iterdir() if p.is_file())
    except OSError:
        return ""
    return f". Archivos en la partición: {', '.join(presentes) or '(ninguno)'}"


def _is_valid_source_name(path: Path, allowed_suffixes: str | tuple[str, ...]) -> bool:
    if isinstance(allowed_suffixes, str):
        allowed_suffixes = (allowed_suffixes,)
    return (
        not path.is_absolute()
        and path.name == str(path)
        and path.name not in {".", ".."}
        and path.suffix.lower() in allowed_suffixes
    )


def _is_readable(path: Path) -> bool:
    try:
        with path.open("rb"):
            return True
    except OSError:
        return False
