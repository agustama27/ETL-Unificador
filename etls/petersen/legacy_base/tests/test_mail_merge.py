"""
Tests for procesos/mail_merge.py

Tests the email selection logic and enrichment functionality.
"""
import pandas as pd
import pytest
from procesos.mail_merge import build_email_lookup, enrich_with_email


def test_build_email_lookup_empty():
    """Test with empty DataFrame."""
    empty_df = pd.DataFrame()
    result = build_email_lookup(empty_df)
    assert result == {}


def test_build_email_lookup_missing_columns():
    """Test with missing required columns."""
    df = pd.DataFrame({'OTRO': [1, 2, 3]})
    result = build_email_lookup(df)
    assert result == {}


def test_build_email_lookup_single_email():
    """Test with single email per client."""
    df = pd.DataFrame({
        'NUMERO CLIENTE': ['123', '456'],
        'EMAIL': ['test1@example.com', 'test2@example.com']
    })
    result = build_email_lookup(df)
    assert result == {
        '123': 'test1@example.com',
        '456': 'test2@example.com'
    }


def test_build_email_lookup_prioritize_principal():
    """Test prioritization of PRINCIPAL=SI."""
    df = pd.DataFrame({
        'NUMERO CLIENTE': ['123', '123', '123'],
        'EMAIL': ['first@example.com', 'principal@example.com', 'third@example.com'],
        'PRINCIPAL': ['NO', 'SI', 'NO']
    })
    result = build_email_lookup(df)
    assert result == {'123': 'principal@example.com'}


def test_build_email_lookup_prioritize_origen_core():
    """Test prioritization of ORIGEN=CORE when no PRINCIPAL=SI."""
    df = pd.DataFrame({
        'NUMERO CLIENTE': ['123', '123', '123'],
        'EMAIL': ['first@example.com', 'core@example.com', 'third@example.com'],
        'PRINCIPAL': ['NO', 'NO', 'NO'],
        'ORIGEN': ['GDD', 'CORE', 'ENGAGE']
    })
    result = build_email_lookup(df)
    assert result == {'123': 'core@example.com'}


def test_build_email_lookup_prioritize_activo():
    """Test prioritization of ESTADO=ACTIVO."""
    df = pd.DataFrame({
        'NUMERO CLIENTE': ['123', '123'],
        'EMAIL': ['inactive@example.com', 'active@example.com'],
        'ESTADO': ['INACTIVO', 'ACTIVO'],
        'PRINCIPAL': ['NO', 'NO']
    })
    result = build_email_lookup(df)
    assert result == {'123': 'active@example.com'}


def test_build_email_lookup_tie_breaker_email_sort():
    """Test tie-breaker by EMAIL ascending when all else equal."""
    df = pd.DataFrame({
        'NUMERO CLIENTE': ['123', '123', '123'],
        'EMAIL': ['zebra@example.com', 'alpha@example.com', 'middle@example.com'],
        'PRINCIPAL': ['NO', 'NO', 'NO'],
        'ESTADO': ['ACTIVO', 'ACTIVO', 'ACTIVO'],
        'ORIGEN': ['CORE', 'CORE', 'CORE']
    })
    result = build_email_lookup(df)
    assert result == {'123': 'alpha@example.com'}


def test_build_email_lookup_combined_priority():
    """Test combined priority: ACTIVO > PRINCIPAL > ORIGEN > EMAIL sort."""
    df = pd.DataFrame({
        'NUMERO CLIENTE': ['123', '123', '123', '123'],
        'EMAIL': ['e1@example.com', 'e2@example.com', 'e3@example.com', 'e4@example.com'],
        'ESTADO': ['INACTIVO', 'ACTIVO', 'ACTIVO', 'ACTIVO'],
        'PRINCIPAL': ['SI', 'NO', 'SI', 'NO'],
        'ORIGEN': ['CORE', 'CORE', 'GDD', 'CORE']
    })
    result = build_email_lookup(df)
    # ACTIVO filters out first row
    # Among ACTIVO rows: PRINCIPAL=SI wins (e3@example.com)
    assert result == {'123': 'e3@example.com'}


def test_build_email_lookup_normalization():
    """Test that NUMERO CLIENTE and EMAIL are normalized."""
    df = pd.DataFrame({
        'NUMERO CLIENTE': ['  123  ', '456'],
        'EMAIL': ['  TEST@EXAMPLE.COM  ', 'lower@example.com']
    })
    result = build_email_lookup(df)
    assert result == {
        '123': 'test@example.com',  # Normalized: trimmed and lowercased
        '456': 'lower@example.com'
    }


def test_build_email_lookup_skip_empty_emails():
    """Test that empty emails are skipped."""
    df = pd.DataFrame({
        'NUMERO CLIENTE': ['123', '456', '789'],
        'EMAIL': ['valid@example.com', '', 'another@example.com']
    })
    result = build_email_lookup(df)
    # Client 456 should be excluded (empty email)
    assert result == {
        '123': 'valid@example.com',
        '789': 'another@example.com'
    }


def test_enrich_with_email_empty_consolidated():
    """Test enrichment with empty consolidated DataFrame."""
    consolidated_df = pd.DataFrame()
    mailcli_df = pd.DataFrame({
        'NUMERO CLIENTE': ['123'],
        'EMAIL': ['test@example.com']
    })
    result = enrich_with_email(consolidated_df, mailcli_df)
    assert result.empty


def test_enrich_with_email_missing_client_key():
    """Test enrichment when client_key column is missing."""
    consolidated_df = pd.DataFrame({'OTRO': [1, 2, 3]})
    mailcli_df = pd.DataFrame({
        'NUMERO CLIENTE': ['123'],
        'EMAIL': ['test@example.com']
    })
    result = enrich_with_email(consolidated_df, mailcli_df, client_key='DAT3')
    assert 'email_registrado' in result.columns
    assert (result['email_registrado'] == '').all()


def test_enrich_with_email_no_mailcli():
    """Test enrichment when mailcli_df is None."""
    consolidated_df = pd.DataFrame({
        'DAT3': ['123', '456', '789'],
        'NOMBRE': ['Cliente A', 'Cliente B', 'Cliente C']
    })
    result = enrich_with_email(consolidated_df, None, client_key='DAT3')
    assert 'email_registrado' in result.columns
    assert (result['email_registrado'] == '').all()


def test_enrich_with_email_with_matches():
    """Test enrichment with matching clients."""
    consolidated_df = pd.DataFrame({
        'DAT3': ['123', '456', '789'],
        'NOMBRE': ['Cliente A', 'Cliente B', 'Cliente C']
    })
    mailcli_df = pd.DataFrame({
        'NUMERO CLIENTE': ['123', '789'],
        'EMAIL': ['cliente_a@example.com', 'cliente_c@example.com']
    })
    result = enrich_with_email(consolidated_df, mailcli_df, client_key='DAT3')

    assert 'email_registrado' in result.columns
    assert result.loc[result['DAT3'] == '123', 'email_registrado'].iloc[0] == 'cliente_a@example.com'
    assert result.loc[result['DAT3'] == '456', 'email_registrado'].iloc[0] == ''
    assert result.loc[result['DAT3'] == '789', 'email_registrado'].iloc[0] == 'cliente_c@example.com'


def test_enrich_with_email_priority_applied():
    """Test that priority rules are applied during enrichment."""
    consolidated_df = pd.DataFrame({
        'DAT3': ['123'],
        'NOMBRE': ['Cliente A']
    })
    mailcli_df = pd.DataFrame({
        'NUMERO CLIENTE': ['123', '123'],
        'EMAIL': ['old@example.com', 'principal@example.com'],
        'PRINCIPAL': ['NO', 'SI']
    })
    result = enrich_with_email(consolidated_df, mailcli_df, client_key='DAT3')

    assert 'email_registrado' in result.columns
    assert result.loc[result['DAT3'] == '123', 'email_registrado'].iloc[0] == 'principal@example.com'


def test_enrich_with_email_normalization():
    """Test that client ID normalization works during join."""
    consolidated_df = pd.DataFrame({
        'DAT3': ['  123  ', '456'],  # With spaces
        'NOMBRE': ['Cliente A', 'Cliente B']
    })
    mailcli_df = pd.DataFrame({
        'NUMERO CLIENTE': ['123', '456'],  # Without spaces
        'EMAIL': ['a@example.com', 'b@example.com']
    })
    result = enrich_with_email(consolidated_df, mailcli_df, client_key='DAT3')

    assert 'email_registrado' in result.columns
    # Should match despite whitespace differences
    assert (result['email_registrado'] != '').all()
