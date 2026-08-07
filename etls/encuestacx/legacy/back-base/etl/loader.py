"""
Data loading module for writing CSV files.
"""
import csv
import pandas as pd
from pathlib import Path
from typing import Optional
from datetime import datetime
from config import ETLConfig
from utils.logger import get_logger


class LoadError(Exception):
    """Base exception for loading errors."""
    pass


class WritePermissionError(LoadError):
    """Raised when file cannot be written due to permissions."""
    pass


class CSVLoader:
    """Load transformed data to CSV files."""

    def __init__(self, config: ETLConfig):
        """
        Initialize loader with configuration.

        Args:
            config: ETL configuration instance
        """
        self.config = config
        self.logger = get_logger('etl.loader')

    def load(
        self,
        df: pd.DataFrame,
        output_path: Optional[Path] = None,
        create_backup: bool = True,
        e164_format: bool = False
    ) -> Path:
        """
        Load dataframe to CSV file.

        Args:
            df: Transformed dataframe to save
            output_path: Output file path (uses config default if None)
            create_backup: Whether to create timestamped backup file
            e164_format: If True, add + prefix to phone numbers for E.164 format

        Returns:
            Path to the saved CSV file

        Raises:
            LoadError: If file cannot be written
        """
        if output_path is None:
            output_path = self.config.OUTPUT_FILE

        # Create a copy to avoid modifying original dataframe
        df_output = df.copy()

        # Add + prefix to phone numbers for E.164 format
        if e164_format and 'phone number' in df_output.columns:
            df_output['phone number'] = df_output['phone number'].apply(
                lambda x: f'+{x}' if pd.notna(x) and str(x).strip() and not str(x).startswith('+') else x
            )
            self.logger.info("Applied E.164 format: added + prefix to phone numbers")

        self.logger.info(f"Loading {len(df_output)} rows to CSV: {output_path}")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Write CSV file (minimal quotes - only for fields with commas)
            df_output.to_csv(
                output_path,
                sep=self.config.CSV_DELIMITER,
                encoding=self.config.CSV_ENCODING,
                index=False,
                quoting=csv.QUOTE_MINIMAL
            )

            # Verify file was created
            if not output_path.exists():
                raise LoadError(f"CSV file was not created: {output_path}")

            file_size = output_path.stat().st_size
            self.logger.info(f"Successfully saved CSV: {output_path} ({file_size:,} bytes)")

            # Create backup with timestamp
            if create_backup:
                backup_path = self._create_backup(df_output, output_path)
                self.logger.debug(f"Created backup: {backup_path}")

            return output_path

        except PermissionError as e:
            raise WritePermissionError(f"Permission denied writing to {output_path}: {e}")
        except Exception as e:
            raise LoadError(f"Failed to write CSV: {e}")

    def _create_backup(self, df: pd.DataFrame, original_path: Path) -> Path:
        """
        Create timestamped backup of CSV file.

        Args:
            df: Dataframe to save
            original_path: Original file path

        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{original_path.stem}_{timestamp}{original_path.suffix}"
        backup_path = original_path.parent / backup_name

        try:
            df.to_csv(
                backup_path,
                sep=self.config.CSV_DELIMITER,
                encoding=self.config.CSV_ENCODING,
                index=False,
                quoting=csv.QUOTE_MINIMAL
            )
            return backup_path
        except Exception as e:
            self.logger.warning(f"Failed to create backup: {e}")
            return None

    def validate_csv(self, file_path: Path) -> bool:
        """
        Validate that CSV file was written correctly.

        Args:
            file_path: Path to CSV file

        Returns:
            True if valid, False otherwise
        """
        try:
            # Try to read the CSV back
            df = pd.read_csv(
                file_path,
                sep=self.config.CSV_DELIMITER,
                encoding=self.config.CSV_ENCODING
            )

            # Check columns match expected output
            expected_cols = set(self.config.OUTPUT_COLUMNS)
            actual_cols = set(df.columns)

            if expected_cols != actual_cols:
                missing = expected_cols - actual_cols
                extra = actual_cols - expected_cols
                self.logger.error(f"Column mismatch. Missing: {missing}, Extra: {extra}")
                return False

            self.logger.debug(f"CSV validation passed: {len(df)} rows, {len(df.columns)} columns")
            return True

        except Exception as e:
            self.logger.error(f"CSV validation failed: {e}")
            return False

    def get_file_info(self, file_path: Path) -> dict:
        """
        Get information about saved CSV file.

        Args:
            file_path: Path to CSV file

        Returns:
            Dictionary with file information
        """
        if not file_path.exists():
            return {'exists': False}

        stat = file_path.stat()
        df = pd.read_csv(file_path, sep=self.config.CSV_DELIMITER)

        return {
            'exists': True,
            'path': str(file_path),
            'size_bytes': stat.st_size,
            'size_kb': round(stat.st_size / 1024, 2),
            'rows': len(df),
            'columns': len(df.columns),
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        }
