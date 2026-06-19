"""
Unit tests for phone_normalizer module.

Tests the phone normalization logic to ensure it matches
the n8n workflow JavaScript implementation exactly.
"""
import pytest
import pandas as pd
from utils.phone_normalizer import normalize_phone, normalize_phone_series


class TestNormalizePhone:
    """Test cases for normalize_phone function."""

    def test_normalize_with_plus_sign(self):
        """Test normalization of phone with + prefix."""
        assert normalize_phone("+54 9 11 1234-5678") == "5491112345678"
        assert normalize_phone("+351 284 3724") == "3512843724"
        assert normalize_phone("+1234567890") == "1234567890"

    def test_normalize_with_spaces(self):
        """Test normalization of phone with spaces."""
        assert normalize_phone("351 284 3724") == "3512843724"
        assert normalize_phone("11 1234 5678") == "1112345678"
        assert normalize_phone("  123 456 789  ") == "123456789"

    def test_normalize_with_dashes(self):
        """Test normalization of phone with dashes."""
        assert normalize_phone("11-1234-5678") == "1112345678"
        assert normalize_phone("123-456-789") == "123456789"
        assert normalize_phone("1234-5678") == "12345678"

    def test_normalize_with_parentheses(self):
        """Test normalization of phone with parentheses."""
        assert normalize_phone("(351) 284-3724") == "3512843724"
        assert normalize_phone("(11) 1234-5678") == "1112345678"

    def test_normalize_decimal_format(self):
        """Test normalization of phone in decimal format (from Excel)."""
        assert normalize_phone("3454400185.0") == "3454400185"
        assert normalize_phone("1234567890.0") == "1234567890"
        assert normalize_phone("123.456") == "123"

    def test_normalize_integer(self):
        """Test normalization of phone as integer."""
        assert normalize_phone(3454400185) == "3454400185"
        assert normalize_phone(1234567890) == "1234567890"

    def test_normalize_float(self):
        """Test normalization of phone as float."""
        assert normalize_phone(3454400185.0) == "3454400185"
        assert normalize_phone(1234567890.0) == "1234567890"

    def test_normalize_null_values(self):
        """Test normalization of null/None values."""
        assert normalize_phone(None) == ""
        assert normalize_phone("") == ""
        assert normalize_phone(float('nan')) == ""

    def test_normalize_empty_string(self):
        """Test normalization of empty string."""
        assert normalize_phone("") == ""
        assert normalize_phone("  ") == ""
        assert normalize_phone("\t") == ""

    def test_normalize_with_special_characters(self):
        """Test normalization of phone with various special characters."""
        assert normalize_phone("+54-9-11-1234-5678") == "5491112345678"
        assert normalize_phone("(+54) 9 11 1234-5678") == "5491112345678"
        assert normalize_phone("tel: +351 284 3724") == "3512843724"

    def test_normalize_with_letters(self):
        """Test normalization removes letters."""
        assert normalize_phone("123abc456def") == "123456"
        assert normalize_phone("phone: 1234567890") == "1234567890"

    def test_normalize_already_normalized(self):
        """Test normalization of already normalized phone."""
        assert normalize_phone("1234567890") == "1234567890"
        assert normalize_phone("5491112345678") == "5491112345678"

    def test_normalize_real_world_examples(self):
        """Test normalization with real-world phone formats."""
        # Argentina format
        assert normalize_phone("+54 9 11 4567-8901") == "5491145678901"
        # Portugal format
        assert normalize_phone("+351 284 3724") == "3512843724"
        # US format
        assert normalize_phone("+1 (555) 123-4567") == "15551234567"
        # Excel decimal format
        assert normalize_phone("3454400185.0") == "3454400185"


class TestNormalizePhoneSeries:
    """Test cases for normalize_phone_series function."""

    def test_normalize_series_basic(self):
        """Test normalization of pandas Series."""
        series = pd.Series([
            "+54 9 11 1234-5678",
            "351 284 3724",
            "3454400185.0"
        ])
        result = normalize_phone_series(series)

        assert result[0] == "5491112345678"
        assert result[1] == "3512843724"
        assert result[2] == "3454400185"

    def test_normalize_series_with_nulls(self):
        """Test normalization of Series with null values."""
        series = pd.Series([
            "+54 9 11 1234-5678",
            None,
            "",
            "3454400185.0"
        ])
        result = normalize_phone_series(series)

        assert result[0] == "5491112345678"
        assert result[1] == ""
        assert result[2] == ""
        assert result[3] == "3454400185"

    def test_normalize_series_mixed_types(self):
        """Test normalization of Series with mixed types."""
        series = pd.Series([
            "+54 9 11 1234-5678",
            3454400185,
            "351 284 3724",
            3454400185.0
        ])
        result = normalize_phone_series(series)

        assert result[0] == "5491112345678"
        assert result[1] == "3454400185"
        assert result[2] == "3512843724"
        assert result[3] == "3454400185"

    def test_normalize_empty_series(self):
        """Test normalization of empty Series."""
        series = pd.Series([], dtype=object)
        result = normalize_phone_series(series)

        assert len(result) == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_very_long_phone(self):
        """Test normalization of very long phone number."""
        long_phone = "1234567890123456789012345"
        result = normalize_phone(long_phone)
        assert result == long_phone
        assert result.isdigit()

    def test_very_short_phone(self):
        """Test normalization of very short phone number."""
        assert normalize_phone("123") == "123"
        assert normalize_phone("1") == "1"

    def test_only_special_characters(self):
        """Test normalization of string with only special characters."""
        assert normalize_phone("+++---()()()") == ""
        assert normalize_phone("   ") == ""
        assert normalize_phone("---") == ""

    def test_unicode_characters(self):
        """Test normalization handles unicode characters."""
        assert normalize_phone("123₄567") == "123567"  # Unicode subscript removed
        assert normalize_phone("123\u00a0456") == "123456"  # Non-breaking space

    def test_multiple_decimal_points(self):
        """Test normalization with multiple decimal points."""
        assert normalize_phone("123.456.789") == "123"
        assert normalize_phone("1.2.3.4") == "1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
