"""Orquestación del ETL: extract() -> transform() -> load()."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import schema
from .config import PipelineConfig
from .extractors import ExtractionDiagnostics, extract_all_sources
from .loaders import ApproachLoader, RomanCsvLoader
from .transformers import (
    ClientPhoneDirectory,
    build_detail,
    consolidate_by_client,
    resolve_duplicate_clients,
)


@dataclass
class ExtractResult:
    saldos_generales: pd.DataFrame
    maquinarias: pd.DataFrame
    remitos_repuestos: pd.DataFrame
    remitos_servicios: pd.DataFrame
    diagnostics: ExtractionDiagnostics = field(
        default_factory=lambda: ExtractionDiagnostics({}, {})
    )

    def all_sources(self) -> tuple[pd.DataFrame, ...]:
        return (
            self.saldos_generales,
            self.maquinarias,
            self.remitos_repuestos,
            self.remitos_servicios,
        )


@dataclass
class TransformResult:
    detalle: pd.DataFrame
    consolidado: pd.DataFrame


@dataclass
class LoadResult:
    roman_path: Path
    approach_path: Path
    diagnostics: ExtractionDiagnostics


def extract(config: PipelineConfig) -> ExtractResult:
    source_extractions = tuple(extract_all_sources(
        config.saldos_generales_path,
        config.maquinarias_path,
        config.remitos_repuestos_path,
        config.remitos_servicios_path,
    ))
    saldos, maquinarias, repuestos, servicios = (item.rows for item in source_extractions)
    excluded_ars = {
        source: item.diagnostics.excluded_ars_by_source[source]
        for item in source_extractions
        for source in item.diagnostics.excluded_ars_by_source
    }
    excluded_unknown = {
        source: item.diagnostics.excluded_unknown_by_source[source]
        for item in source_extractions
        for source in item.diagnostics.excluded_unknown_by_source
    }
    diagnostics = ExtractionDiagnostics(excluded_ars, excluded_unknown)
    if any(excluded_ars.values()):
        import logging
        logging.getLogger(__name__).warning(diagnostics.summary())
    return ExtractResult(
        saldos_generales=saldos,
        maquinarias=maquinarias,
        remitos_repuestos=repuestos,
        remitos_servicios=servicios,
        diagnostics=diagnostics,
    )


def transform(extracted: ExtractResult, config: PipelineConfig) -> TransformResult:
    phone_directory = ClientPhoneDirectory()
    phone_directory.register(
        [extracted.saldos_generales, extracted.maquinarias],
        config.telefono_min_digitos,
        config.telefono_max_digitos,
    )

    # El teléfono se resuelve antes de deduplicar: es una de las dos
    # evidencias que permiten decidir si dos claves son el mismo cliente.
    detalle = resolve_duplicate_clients(
        build_detail(extracted.all_sources(), phone_directory, config)
    )
    consolidado = consolidate_by_client(detalle, phone_directory)
    return TransformResult(detalle=detalle, consolidado=consolidado)


def verify_phone_parity(roman_rows: pd.DataFrame, approach_rows: pd.DataFrame) -> None:
    """El E1KIA es exactamente el universo llamable del Roman: mismo
    conjunto de teléfonos, sin repetidos.

    Se chequea antes de escribir, no después, para que una corrida rota no
    deje archivos parciales. Si esto se rompiera, gestión y plataforma de
    llamadas estarían trabajando sobre poblaciones distintas — y nadie se
    daría cuenta hasta que un cliente reclame una llamada que no recibió.
    """
    roman_phones = set(roman_rows[schema.OUT_TELEFONO_CLIENTE].dropna())
    approach_phones = list(approach_rows[schema.OUT_TELEFONO_CLIENTE])

    repetidos = len(approach_phones) - len(set(approach_phones))
    if repetidos:
        raise ValueError(f"E1KIA: {repetidos} telefono(s) repetido(s) en el marcador")

    faltantes = roman_phones - set(approach_phones)
    sobrantes = set(approach_phones) - roman_phones
    if faltantes or sobrantes:
        raise ValueError(
            f"E1KIA y Roman no coinciden en TelefonoCliente: "
            f"{len(faltantes)} faltante(s) en el E1KIA, {len(sobrantes)} sobrante(s)"
        )


def load(
    transformed: TransformResult,
    config: PipelineConfig,
    diagnostics: ExtractionDiagnostics | None = None,
) -> LoadResult:
    roman_path = config.roman_output_path
    approach_path = config.approach_output_path
    existing_targets = [
        path for path in (roman_path, approach_path) if path.exists() or path.is_symlink()
    ]
    if existing_targets and not config.overwrite:
        names = ", ".join(path.name for path in existing_targets)
        raise FileExistsError(f"Ya existen exportaciones para esta corrida: {names}")

    roman_loader = RomanCsvLoader()
    approach_loader = ApproachLoader()
    verify_phone_parity(
        roman_loader.rows_to_export(transformed.consolidado),
        approach_loader.rows_to_export(transformed.consolidado),
    )

    config.output_dir.mkdir(parents=True, exist_ok=True)
    roman_loader.save(transformed.consolidado, roman_path)
    approach_loader.save(transformed.consolidado, approach_path)

    return LoadResult(
        roman_path=roman_path,
        approach_path=approach_path,
        diagnostics=diagnostics or ExtractionDiagnostics({}, {}),
    )


def run_pipeline(config: PipelineConfig) -> LoadResult:
    extracted = extract(config)
    transformed = transform(extracted, config)
    return load(transformed, config, extracted.diagnostics)
