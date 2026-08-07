"""
Módulo de configuración del sistema
Carga variables de entorno y configura logging
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime


@dataclass
class Config:
    """Configuración del sistema"""
    retell_api_key: str
    retell_base_url: str
    retell_folder: Path
    roman_folder: Path
    results_folder: Path
    log_level: str


def load_config(require_api_key: bool = True) -> Config:
    """
    Cargar y validar configuración desde .env

    Returns:
        Config: Objeto de configuración

    Raises:
        ValueError: Si RETELL_API_KEY no está configurada
    """
    # Cargar .env
    load_dotenv()

    # Obtener API key (requerida solo en comandos que llaman la API)
    api_key = os.getenv('RETELL_API_KEY')
    if require_api_key and (not api_key or api_key == 'tu_api_key_aqui'):
        raise ValueError(
            "RETELL_API_KEY no configurada. "
            "Por favor, edite el archivo .env con su API key de Retell."
        )

    # Obtener otras configuraciones con defaults
    base_url = os.getenv('RETELL_BASE_URL', 'https://api.retellai.com/v2')
    log_level = os.getenv('LOG_LEVEL', 'INFO')

    # Obtener paths de carpetas (relativos a back-resultados/)
    base_path = Path(__file__).parent / 'back-resultados'
    retell_folder = base_path / os.getenv('RETELL_FOLDER', 'retell')
    roman_folder = base_path / os.getenv('ROMAN_FOLDER', 'roman')
    results_folder = base_path / os.getenv('RESULTS_FOLDER', 'results')

    # Crear carpetas si no existen
    retell_folder.mkdir(parents=True, exist_ok=True)
    roman_folder.mkdir(parents=True, exist_ok=True)
    results_folder.mkdir(parents=True, exist_ok=True)

    return Config(
        retell_api_key=api_key or '',
        retell_base_url=base_url,
        retell_folder=retell_folder,
        roman_folder=roman_folder,
        results_folder=results_folder,
        log_level=log_level
    )


def setup_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    Configurar logger con formato estándar

    Args:
        name: Nombre del logger (normalmente __name__ del módulo)
        log_file: Path al archivo de log (opcional)

    Returns:
        logging.Logger: Logger configurado
    """
    logger = logging.getLogger(name)

    # Evitar duplicar handlers si ya está configurado
    if logger.handlers:
        return logger

    # Obtener nivel de log desde env o usar INFO por defecto
    log_level_str = os.getenv('LOG_LEVEL', 'INFO')
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Formato de log
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler para consola (INFO y superior)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler para archivo (todos los niveles)
    if log_file:
        file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_log_file_path() -> Path:
    """
    Generar path para archivo de log con timestamp

    Returns:
        Path: Path al archivo de log
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f'process_{timestamp}.log'

    # Crear carpeta results si no existe
    results_folder = Path(__file__).parent / 'back-resultados' / 'results'
    results_folder.mkdir(parents=True, exist_ok=True)

    return results_folder / log_filename
