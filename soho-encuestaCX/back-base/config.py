"""
Configuration management for ETL pipeline.
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class ETLConfig:
    """Central configuration for the ETL pipeline."""

    # Base paths
    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    INPUT_DIR: Path = field(init=False)
    OUTPUT_DIR: Path = field(init=False)
    LOG_DIR: Path = field(init=False)

    # File paths
    INPUT_FILE: Path = field(init=False)
    OUTPUT_FILE: Path = field(init=False)
    OUTPUT_FILE_E164: Path = field(init=False)  # E.164 format with + prefix

    # CSV settings
    CSV_DELIMITER: str = ','
    CSV_ENCODING: str = 'utf-8-sig'  # UTF-8 with BOM for n8n compatibility

    # Input column names (as they appear in Excel)
    INPUT_COLUMNS: List[str] = field(default_factory=lambda: [
        'Tier',
        'Cliente',
        'Gerencia Cliente',
        'Vertical de negocio',
        'Nombre',
        'Apellido',
        'Puesto',
        'Referente',
        'Jerarquia',
        'Mail',
        'Teléfono',
        'Provincia',
        'País',
        'Evoltis: Referente operativo',
        'Evoltis: Referente de negocio'
    ])

    # Output column names (matching n8n workflow expected format)
    OUTPUT_COLUMNS: List[str] = field(default_factory=lambda: [
        'Status de encuesta',
        'Tier',
        'cliente',
        'Gerencia Cliente',
        'Vertical de negocio',
        'customer_name',
        'Puesto',
        'Referente',
        'Jerarquia',
        'Mail',
        'phone number',
        'Provincia',
        'País',
        'Evoltis: Referente operativo',
        'Evoltis: Referente de negocio'
    ])

    # Column mapping from input to output
    COLUMN_MAPPING: Dict[str, str] = field(default_factory=lambda: {
        'Tier': 'Tier',
        'Cliente': 'cliente',
        'Gerencia Cliente': 'Gerencia Cliente',
        'Vertical de negocio': 'Vertical de negocio',
        'Puesto': 'Puesto',
        'Referente': 'Referente',
        'Jerarquia': 'Jerarquia',
        'Mail': 'Mail',
        'Provincia': 'Provincia',
        'País': 'País',
        'Evoltis: Referente operativo': 'Evoltis: Referente operativo',
        'Evoltis: Referente de negocio': 'Evoltis: Referente de negocio'
    })

    # Required fields (must not be empty in output)
    REQUIRED_FIELDS: List[str] = field(default_factory=lambda: [
        'Tier',
        'cliente',
        'customer_name',
        'Mail',
        'phone number'
    ])

    # Logging
    LOG_LEVEL: str = 'INFO'
    LOG_FORMAT: str = '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
    LOG_DATE_FORMAT: str = '%Y-%m-%d %H:%M:%S'

    def __post_init__(self):
        """Initialize derived paths after dataclass initialization."""
        self.INPUT_DIR = self.BASE_DIR / "input"
        self.OUTPUT_DIR = self.BASE_DIR / "output"
        self.LOG_DIR = self.BASE_DIR / "logs"

        self.INPUT_FILE = self.INPUT_DIR / "Entrevista CX 2° semestre 2025.xlsx"
        self.OUTPUT_FILE = self.OUTPUT_DIR / "base_encuesta.csv"
        self.OUTPUT_FILE_E164 = self.OUTPUT_DIR / "base_encuesta_e164.csv"  # With + prefix

        # Create directories if they don't exist
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)


# Singleton instance
config = ETLConfig()
