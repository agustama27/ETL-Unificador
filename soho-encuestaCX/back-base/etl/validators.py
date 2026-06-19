"""
Data validation module for ensuring data quality.
"""
import pandas as pd
import re
from typing import List, Tuple
from dataclasses import dataclass
from email_validator import validate_email, EmailNotValidError
from config import ETLConfig
from utils.logger import get_logger


@dataclass
class ValidationReport:
    """Report of validation results."""
    total_rows: int
    valid_rows: int
    warning_rows: int
    error_rows: int
    warnings: List[str]
    errors: List[str]

    @property
    def passed(self) -> int:
        """Number of rows that passed validation."""
        return self.valid_rows

    @property
    def has_errors(self) -> bool:
        """Whether validation found any errors."""
        return self.error_rows > 0

    def __str__(self) -> str:
        """String representation of the report."""
        return (
            f"ValidationReport(\n"
            f"  Total rows: {self.total_rows}\n"
            f"  Valid: {self.valid_rows}\n"
            f"  Warnings: {self.warning_rows}\n"
            f"  Errors: {self.error_rows}\n"
            f")"
        )


class DataValidator:
    """Validate transformed data quality."""

    def __init__(self, config: ETLConfig):
        """
        Initialize validator with configuration.

        Args:
            config: ETL configuration instance
        """
        self.config = config
        self.logger = get_logger('etl.validator')

    def validate(self, df: pd.DataFrame) -> ValidationReport:
        """
        Validate transformed dataframe.

        Checks:
        - Required fields are not empty
        - Email format is valid
        - Phone numbers contain only digits
        - No completely empty rows

        Args:
            df: Transformed dataframe to validate

        Returns:
            ValidationReport with results
        """
        self.logger.info(f"Validating {len(df)} rows")

        total_rows = len(df)
        warnings = []
        errors = []
        warning_rows = 0
        error_rows = 0

        # Validate required fields
        for field in self.config.REQUIRED_FIELDS:
            if field not in df.columns:
                errors.append(f"Required column '{field}' missing from dataframe")
                error_rows = total_rows
                continue

            empty_count = (df[field] == '').sum()
            if empty_count > 0:
                msg = f"Field '{field}' is empty in {empty_count} rows"
                warnings.append(msg)
                warning_rows = max(warning_rows, empty_count)
                self.logger.warning(msg)

        # Validate email format
        if 'Mail' in df.columns:
            invalid_emails = self._validate_emails(df['Mail'])
            if invalid_emails:
                msg = f"Invalid email format in {len(invalid_emails)} rows"
                warnings.append(msg)
                warning_rows = max(warning_rows, len(invalid_emails))
                self.logger.warning(msg)
                for idx, email in invalid_emails[:5]:  # Log first 5
                    self.logger.debug(f"  Row {idx}: '{email}'")

        # Validate phone numbers
        if 'phone number' in df.columns:
            invalid_phones = self._validate_phone_numbers(df['phone number'])
            if invalid_phones:
                msg = f"Invalid phone format in {len(invalid_phones)} rows"
                warnings.append(msg)
                warning_rows = max(warning_rows, len(invalid_phones))
                self.logger.warning(msg)
                for idx, phone in invalid_phones[:5]:  # Log first 5
                    self.logger.debug(f"  Row {idx}: '{phone}'")

        # Calculate valid rows
        valid_rows = total_rows - max(warning_rows, error_rows)

        report = ValidationReport(
            total_rows=total_rows,
            valid_rows=valid_rows,
            warning_rows=warning_rows,
            error_rows=error_rows,
            warnings=warnings,
            errors=errors
        )

        self.logger.info(f"Validation complete: {report.valid_rows}/{report.total_rows} valid rows")
        if warnings:
            self.logger.warning(f"Found {len(warnings)} validation warnings")
        if errors:
            self.logger.error(f"Found {len(errors)} validation errors")

        return report

    def _validate_emails(self, email_series: pd.Series) -> List[Tuple[int, str]]:
        """
        Validate email addresses.

        Args:
            email_series: Series of email addresses

        Returns:
            List of (index, email) tuples for invalid emails
        """
        invalid_emails = []

        for idx, email in email_series.items():
            if email == '' or pd.isna(email):
                continue  # Empty emails are handled by required field validation

            # Basic format check
            if not self._is_valid_email_format(email):
                invalid_emails.append((idx, email))

        return invalid_emails

    def _is_valid_email_format(self, email: str) -> bool:
        """
        Check if email has valid format.

        Args:
            email: Email address to validate

        Returns:
            True if valid format, False otherwise
        """
        try:
            # Use email-validator library
            validate_email(email)
            return True
        except EmailNotValidError:
            # Fallback to basic regex
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return bool(re.match(pattern, email))

    def _validate_phone_numbers(self, phone_series: pd.Series) -> List[Tuple[int, str]]:
        """
        Validate phone numbers (should be digits only after normalization).

        Args:
            phone_series: Series of phone numbers

        Returns:
            List of (index, phone) tuples for invalid phones
        """
        invalid_phones = []

        for idx, phone in phone_series.items():
            if phone == '' or pd.isna(phone):
                continue  # Empty phones are handled by required field validation

            # After normalization, should contain only digits
            if not phone.isdigit():
                invalid_phones.append((idx, phone))
                continue

            # Check reasonable length (8-15 digits for international)
            if len(phone) < 8 or len(phone) > 15:
                invalid_phones.append((idx, phone))

        return invalid_phones

    def validate_columns(self, df: pd.DataFrame) -> bool:
        """
        Validate that all required output columns exist.

        Args:
            df: DataFrame to validate

        Returns:
            True if all columns exist, False otherwise
        """
        missing_columns = set(self.config.OUTPUT_COLUMNS) - set(df.columns)
        if missing_columns:
            self.logger.error(f"Missing output columns: {missing_columns}")
            return False
        return True
