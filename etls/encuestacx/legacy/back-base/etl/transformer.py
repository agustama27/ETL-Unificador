"""
Data transformation module for applying business logic.
"""
import pandas as pd
from typing import Optional
from config import ETLConfig
from utils.logger import get_logger
from utils.phone_normalizer import normalize_phone_series


class TransformationError(Exception):
    """Base exception for transformation errors."""
    pass


class DataTransformer:
    """Transform extracted data according to business rules."""

    def __init__(self, config: ETLConfig):
        """
        Initialize transformer with configuration.

        Args:
            config: ETL configuration instance
        """
        self.config = config
        self.logger = get_logger('etl.transformer')

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply all transformations to the dataframe.

        Transformations applied:
        1. Create customer_name from Nombre + Apellido
        2. Normalize phone_number from Teléfono
        3. Map input columns to output columns
        4. Clean and format data

        Args:
            df: Input dataframe with Excel data

        Returns:
            Transformed dataframe ready for loading

        Raises:
            TransformationError: If transformation fails
        """
        self.logger.info(f"Starting transformation of {len(df)} rows")

        try:
            # Create a copy to avoid modifying original
            df_transformed = df.copy()

            # Step 1: Create customer_name
            self.logger.debug("Creating customer_name field")
            df_transformed['customer_name'] = self._create_customer_name(
                df_transformed['Nombre'],
                df_transformed['Apellido']
            )

            # Step 2: Normalize phone number
            self.logger.debug("Normalizing phone numbers")
            df_transformed['phone number'] = normalize_phone_series(df_transformed['Teléfono'])

            # Step 2.5: Add Status de encuesta column (empty)
            df_transformed['Status de encuesta'] = ''

            # Step 3: Map columns
            self.logger.debug("Mapping columns to output format")
            df_output = self._map_columns(df_transformed)

            # Step 4: Clean data
            self.logger.debug("Cleaning data")
            df_output = self._clean_data(df_output)

            # Step 5: Select and order output columns
            df_output = df_output[self.config.OUTPUT_COLUMNS]

            self.logger.info(f"Transformation complete: {len(df_output)} rows, {len(df_output.columns)} columns")

            return df_output

        except Exception as e:
            self.logger.error(f"Transformation failed: {e}", exc_info=True)
            raise TransformationError(f"Failed to transform data: {e}")

    def _create_customer_name(
        self,
        nombre_series: pd.Series,
        apellido_series: pd.Series
    ) -> pd.Series:
        """
        Create customer_name by concatenating Nombre + Apellido.

        Handles missing values gracefully:
        - If both exist: "Nombre Apellido"
        - If only one exists: uses the available value
        - If neither exists: empty string

        Args:
            nombre_series: Series with first names
            apellido_series: Series with last names

        Returns:
            Series with concatenated names
        """
        def concat_names(nombre, apellido):
            # Convert to string and strip, handling NaN
            nombre_str = str(nombre).strip() if pd.notna(nombre) else ''
            apellido_str = str(apellido).strip() if pd.notna(apellido) else ''

            # Handle 'nan' string representation
            if nombre_str.lower() == 'nan':
                nombre_str = ''
            if apellido_str.lower() == 'nan':
                apellido_str = ''

            # Concatenate
            if nombre_str and apellido_str:
                return f"{nombre_str} {apellido_str}"
            return nombre_str or apellido_str or ''

        customer_names = pd.Series([
            concat_names(nombre, apellido)
            for nombre, apellido in zip(nombre_series, apellido_series)
        ])

        self.logger.debug(f"Created {len(customer_names)} customer names")
        return customer_names

    def _map_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Map input columns to output column names.

        Args:
            df: DataFrame with input columns

        Returns:
            DataFrame with renamed columns
        """
        # Create new dataframe with mapped columns
        df_mapped = pd.DataFrame()

        # Map direct columns
        for input_col, output_col in self.config.COLUMN_MAPPING.items():
            if input_col in df.columns:
                df_mapped[output_col] = df[input_col]
            else:
                self.logger.warning(f"Column '{input_col}' not found in dataframe")
                df_mapped[output_col] = ''

        # Add new columns (customer_name, phone number, Status de encuesta)
        if 'customer_name' in df.columns:
            df_mapped['customer_name'] = df['customer_name']
        if 'phone number' in df.columns:
            df_mapped['phone number'] = df['phone number']
        if 'Status de encuesta' in df.columns:
            df_mapped['Status de encuesta'] = df['Status de encuesta']

        return df_mapped

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and format data.

        Operations:
        - Strip whitespace from string columns
        - Replace NaN with empty strings
        - Ensure consistent data types

        Args:
            df: DataFrame to clean

        Returns:
            Cleaned DataFrame
        """
        df_clean = df.copy()

        # Replace NaN with empty strings
        df_clean = df_clean.fillna('')

        # Strip whitespace from all string columns
        for col in df_clean.columns:
            # Check for string-like dtypes (object, str, string)
            if df_clean[col].dtype in ['object', 'str', 'string'] or str(df_clean[col].dtype) == 'object':
                df_clean[col] = df_clean[col].astype(str).str.strip()

        return df_clean

    def get_transformation_summary(self, df_input: pd.DataFrame, df_output: pd.DataFrame) -> dict:
        """
        Get summary of transformation.

        Args:
            df_input: Original dataframe
            df_output: Transformed dataframe

        Returns:
            Dictionary with transformation statistics
        """
        return {
            'input_rows': len(df_input),
            'output_rows': len(df_output),
            'input_columns': len(df_input.columns),
            'output_columns': len(df_output.columns),
            'customer_names_created': (df_output['customer_name'] != '').sum(),
            'phone_numbers_normalized': (df_output['phone number'] != '').sum(),
        }
