"""
Unit tests for transformer module.

Tests data transformation logic including name concatenation,
phone normalization, and column mapping.
"""
import pytest
import pandas as pd
from config import ETLConfig
from etl.transformer import DataTransformer


@pytest.fixture
def config():
    """Fixture for ETL configuration."""
    return ETLConfig()


@pytest.fixture
def transformer(config):
    """Fixture for DataTransformer instance."""
    return DataTransformer(config)


@pytest.fixture
def sample_input_df():
    """Fixture for sample input dataframe."""
    return pd.DataFrame({
        'Tier': ['Premium', 'Standard'],
        'Cliente': ['Banco Galicia', 'Santander'],
        'Gerencia Cliente': ['Gerencia A', 'Gerencia B'],
        'Vertical de negocio': ['Banking', 'Finance'],
        'Nombre': ['Carolina', 'Juan'],
        'Apellido': ['Aguirre', 'Pérez'],
        'Puesto': ['Head CCC', 'Manager'],
        'Referente': ['Ref A', 'Ref B'],
        'Jerarquia': ['Senior', 'Mid'],
        'Mail': ['carolina@galicia.com', 'juan@santander.com'],
        'Teléfono': ['+54 9 11 1234-5678', '3454400185.0'],
        'Provincia': ['Buenos Aires', 'Córdoba'],
        'País': ['Argentina', 'Argentina'],
        'Evoltis: Referente operativo': ['Op Ref 1', 'Op Ref 2'],
        'Evoltis: Referente de negocio': ['Biz Ref 1', 'Biz Ref 2']
    })


class TestDataTransformer:
    """Test cases for DataTransformer class."""

    def test_transform_basic(self, transformer, sample_input_df):
        """Test basic transformation."""
        result = transformer.transform(sample_input_df)

        # Check output shape
        assert len(result) == 2
        assert len(result.columns) == 14

        # Check all expected columns exist
        expected_columns = [
            'tier', 'cliente', 'gerencia_cliente', 'vertical_de_negocio',
            'customer_name', 'puesto', 'referente', 'jerarquia', 'mail',
            'phone_number', 'provincia', 'pais', 'referente_operativo',
            'referente_negocio'
        ]
        assert list(result.columns) == expected_columns

    def test_customer_name_creation(self, transformer, sample_input_df):
        """Test customer_name field creation."""
        result = transformer.transform(sample_input_df)

        assert result['customer_name'].iloc[0] == 'Carolina Aguirre'
        assert result['customer_name'].iloc[1] == 'Juan Pérez'

    def test_phone_normalization(self, transformer, sample_input_df):
        """Test phone number normalization."""
        result = transformer.transform(sample_input_df)

        assert result['phone_number'].iloc[0] == '5491112345678'
        assert result['phone_number'].iloc[1] == '3454400185'

    def test_column_mapping(self, transformer, sample_input_df):
        """Test column name mapping."""
        result = transformer.transform(sample_input_df)

        # Check direct mappings
        assert result['tier'].iloc[0] == 'Premium'
        assert result['cliente'].iloc[0] == 'Banco Galicia'
        assert result['gerencia_cliente'].iloc[0] == 'Gerencia A'
        assert result['vertical_de_negocio'].iloc[0] == 'Banking'
        assert result['pais'].iloc[0] == 'Argentina'

    def test_transformation_with_missing_values(self, transformer):
        """Test transformation with missing values."""
        df = pd.DataFrame({
            'Tier': ['Premium', None],
            'Cliente': ['Banco Galicia', 'Santander'],
            'Gerencia Cliente': ['Gerencia A', ''],
            'Vertical de negocio': ['Banking', 'Finance'],
            'Nombre': ['Carolina', None],
            'Apellido': [None, 'Pérez'],
            'Puesto': ['Head CCC', 'Manager'],
            'Referente': ['Ref A', 'Ref B'],
            'Jerarquia': ['Senior', 'Mid'],
            'Mail': ['carolina@galicia.com', ''],
            'Teléfono': ['+54 9 11 1234-5678', None],
            'Provincia': ['Buenos Aires', 'Córdoba'],
            'País': ['Argentina', 'Argentina'],
            'Evoltis: Referente operativo': ['Op Ref 1', 'Op Ref 2'],
            'Evoltis: Referente de negocio': ['Biz Ref 1', 'Biz Ref 2']
        })

        result = transformer.transform(df)

        # Check missing values are handled
        assert result['customer_name'].iloc[0] == 'Carolina'
        assert result['customer_name'].iloc[1] == 'Pérez'
        assert result['phone_number'].iloc[1] == ''


class TestCreateCustomerName:
    """Test cases for _create_customer_name method."""

    def test_both_names_present(self, transformer):
        """Test when both first and last name are present."""
        nombre = pd.Series(['Carolina', 'Juan'])
        apellido = pd.Series(['Aguirre', 'Pérez'])

        result = transformer._create_customer_name(nombre, apellido)

        assert result[0] == 'Carolina Aguirre'
        assert result[1] == 'Juan Pérez'

    def test_only_first_name(self, transformer):
        """Test when only first name is present."""
        nombre = pd.Series(['Carolina', 'Juan'])
        apellido = pd.Series([None, None])

        result = transformer._create_customer_name(nombre, apellido)

        assert result[0] == 'Carolina'
        assert result[1] == 'Juan'

    def test_only_last_name(self, transformer):
        """Test when only last name is present."""
        nombre = pd.Series([None, None])
        apellido = pd.Series(['Aguirre', 'Pérez'])

        result = transformer._create_customer_name(nombre, apellido)

        assert result[0] == 'Aguirre'
        assert result[1] == 'Pérez'

    def test_both_names_missing(self, transformer):
        """Test when both names are missing."""
        nombre = pd.Series([None, None])
        apellido = pd.Series([None, None])

        result = transformer._create_customer_name(nombre, apellido)

        assert result[0] == ''
        assert result[1] == ''

    def test_with_whitespace(self, transformer):
        """Test names with extra whitespace."""
        nombre = pd.Series(['  Carolina  ', 'Juan'])
        apellido = pd.Series(['Aguirre  ', '  Pérez'])

        result = transformer._create_customer_name(nombre, apellido)

        assert result[0] == 'Carolina Aguirre'
        assert result[1] == 'Juan Pérez'

    def test_with_nan_string(self, transformer):
        """Test handling of 'nan' string."""
        nombre = pd.Series(['nan', 'Juan'])
        apellido = pd.Series(['Aguirre', 'nan'])

        result = transformer._create_customer_name(nombre, apellido)

        assert result[0] == 'Aguirre'
        assert result[1] == 'Juan'


class TestCleanData:
    """Test cases for _clean_data method."""

    def test_clean_removes_nan(self, transformer):
        """Test that clean_data replaces NaN with empty strings."""
        df = pd.DataFrame({
            'col1': ['value', None],
            'col2': [None, 'value']
        })

        result = transformer._clean_data(df)

        assert result['col1'].iloc[1] == ''
        assert result['col2'].iloc[0] == ''

    def test_clean_strips_whitespace(self, transformer):
        """Test that clean_data strips whitespace."""
        df = pd.DataFrame({
            'col1': ['  value  ', 'value  '],
            'col2': ['  value', 'value']
        })

        result = transformer._clean_data(df)

        assert result['col1'].iloc[0] == 'value'
        assert result['col1'].iloc[1] == 'value'
        assert result['col2'].iloc[0] == 'value'


class TestTransformationSummary:
    """Test cases for get_transformation_summary method."""

    def test_summary(self, transformer, sample_input_df):
        """Test transformation summary generation."""
        result = transformer.transform(sample_input_df)
        summary = transformer.get_transformation_summary(sample_input_df, result)

        assert summary['input_rows'] == 2
        assert summary['output_rows'] == 2
        assert summary['input_columns'] == 15
        assert summary['output_columns'] == 14
        assert summary['customer_names_created'] == 2
        assert summary['phone_numbers_normalized'] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
