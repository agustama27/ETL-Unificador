"""
Data extraction module for reading Excel files.
"""
import pandas as pd
from pathlib import Path
from typing import Optional
from config import ETLConfig
from utils.logger import get_logger


class ExtractionError(Exception):
    """Base exception for extraction errors."""
    pass


class FileNotFoundError(ExtractionError):
    """Raised when input file is not found."""
    pass


class InvalidFileFormatError(ExtractionError):
    """Raised when file format is invalid."""
    pass


class MissingColumnsError(ExtractionError):
    """Raised when required columns are missing."""
    pass


class ExcelExtractor:
    """Extract data from Excel files."""

    def __init__(self, config: ETLConfig):
        """
        Initialize extractor with configuration.

        Args:
            config: ETL configuration instance
        """
        self.config = config
        self.logger = get_logger('etl.extractor')

    def extract(self, file_path: Optional[Path] = None) -> pd.DataFrame:
        """
        Extract data from Excel file.

        Args:
            file_path: Path to Excel file (uses config default if None)

        Returns:
            DataFrame with extracted data

        Raises:
            FileNotFoundError: If file doesn't exist
            InvalidFileFormatError: If file is not a valid Excel file
            MissingColumnsError: If required columns are missing
        """
        if file_path is None:
            file_path = self.config.INPUT_FILE

        self.logger.info(f"Extracting data from: {file_path}")

        # Validate file exists
        if not file_path.exists():
            raise FileNotFoundError(f"Input file not found: {file_path}")

        # Validate file is readable
        if not file_path.is_file():
            raise InvalidFileFormatError(f"Path is not a file: {file_path}")

        # Read Excel file
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
            self.logger.debug(f"Loaded Excel with shape: {df.shape}")
        except Exception as e:
            raise InvalidFileFormatError(f"Failed to read Excel file: {e}")

        # Validate not empty
        if df.empty:
            raise InvalidFileFormatError("Excel file is empty (no data rows)")

        # Validate expected columns exist
        missing_columns = set(self.config.INPUT_COLUMNS) - set(df.columns)
        if missing_columns:
            self.logger.error(f"Missing columns: {missing_columns}")
            self.logger.debug(f"Expected columns: {self.config.INPUT_COLUMNS}")
            self.logger.debug(f"Found columns: {list(df.columns)}")
            raise MissingColumnsError(
                f"Missing required columns: {missing_columns}. "
                f"Expected {len(self.config.INPUT_COLUMNS)} columns, "
                f"found {len(df.columns)}."
            )

        self.logger.info(f"Successfully extracted {len(df)} rows and {len(df.columns)} columns")

        return df

    def validate_file(self, file_path: Optional[Path] = None) -> bool:
        """
        Validate file without loading data.

        Args:
            file_path: Path to Excel file

        Returns:
            True if file is valid, False otherwise
        """
        if file_path is None:
            file_path = self.config.INPUT_FILE

        try:
            self.extract(file_path)
            return True
        except ExtractionError as e:
            self.logger.warning(f"File validation failed: {e}")
            return False
