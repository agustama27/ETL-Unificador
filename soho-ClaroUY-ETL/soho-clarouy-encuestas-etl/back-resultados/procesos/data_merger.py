"""
Merge inteligente de datos Retell + ROMAN para encuestas Claro Uruguay.

ROMAN tiene prioridad para campos de tipificación, pero Retell es la base canónica.
"""
from dataclasses import dataclass
import pandas as pd

from config_encuesta import (
    CAMPOS_SOBRESCRIBIBLES,
    CAMPOS_PROTEGIDOS,
    VALORES_VACIOS,
    es_valor_valido
)

# ── Constants ──────────────────────────────────────────────────────────────────

# ── Merge Stats ───────────────────────────────────────────────────────────────
@dataclass
class MergeStats:
    """Estadísticas del proceso de merge."""
    total_retell: int = 0
    total_roman: int = 0
    matched: int = 0
    unmatched_retell: int = 0
    unmatched_roman: int = 0
    fields_overwritten: int = 0

# ── Functions ─────────────────────────────────────────────────────────────────

def merge_single_call(retell_row: dict, roman_row: dict | None) -> dict:
    """
    Merge los datos de una llamada individual.
    
    Args:
        retell_row: Datos de Retell
        roman_row: Datos de ROMAN (puede ser None)
    
    Returns:
        Diccionario con datos fusionados
    """
    resultado = retell_row.copy()
    
    if roman_row is None:
        return resultado
    
    for campo in CAMPOS_SOBRESCRIBIBLES:
        if campo not in roman_row:
            continue
        
        valor_roman = roman_row[campo]
        
        if not es_valor_valido(valor_roman):
            continue
        
        valor_retell = resultado.get(campo)
        
        if es_valor_valido(valor_retell) and str(valor_retell) != str(valor_roman):
            pass
        
        resultado[campo] = valor_roman
    
    return resultado


def merge_datos_inteligente(df_retell: pd.DataFrame, df_roman: pd.DataFrame | None) -> tuple[pd.DataFrame, MergeStats]:
    """
    Realiza el merge inteligente entre datos de Retell y ROMAN.
    
    Args:
        df_retell: DataFrame con datos de Retell
        df_roman: DataFrame con datos de ROMAN (puede ser vacío)
    
    Returns:
        Tupla (DataFrame mergeado, MergeStats)
    """
    stats = MergeStats()
    stats.total_retell = len(df_retell)
    
    if df_roman is None or df_roman.empty:
        stats.unmatched_retell = stats.total_retell
        print("  ADVERTENCIA: No hay datos de ROMAN para merge")
        return df_retell, stats
    
    stats.total_roman = len(df_roman)
    
    df_retell = df_retell.copy()
    df_roman = df_roman.copy()
    
    if 'call_id' not in df_retell.columns or 'call_id' not in df_roman.columns:
        print("  ERROR: Columna call_id no encontrada en alguna fuente")
        return df_retell, stats
    
    df_retell['call_id'] = df_retell['call_id'].astype(str).str.strip()
    df_roman['call_id'] = df_roman['call_id'].astype(str).str.strip()
    
    df_retell = df_retell.set_index('call_id')
    df_roman = df_roman.set_index('call_id')
    
    indices_roman = set(df_roman.index)
    indices_retell = set(df_retell.index)
    
    stats.matched = len(indices_retell & indices_roman)
    stats.unmatched_retell = len(indices_retell - indices_roman)
    stats.unmatched_roman = len(indices_roman - indices_retell)
    
    print(f"  Merge stats: {stats.matched} coincidencias, {stats.unmatched_retell} solo Retell, {stats.unmatched_roman} solo ROMAN")
    
    if stats.unmatched_roman > 0:
        print(f"  ADVERTENCIA: {stats.unmatched_roman} registros de ROMAN sin match en Retell serán descartados")
    
    for call_id in indices_retell & indices_roman:
        retell_row = df_retell.loc[call_id].to_dict() if hasattr(df_retell.loc[call_id], 'to_dict') else df_retell.loc[call_id].__dict__
        if isinstance(retell_row, pd.Series):
            retell_row = retell_row.to_dict()
        
        roman_row = df_roman.loc[call_id].to_dict() if hasattr(df_roman.loc[call_id], 'to_dict') else df_roman.loc[call_id].__dict__
        if isinstance(roman_row, pd.Series):
            roman_row = roman_row.to_dict()
        
        merged = merge_single_call(retell_row, roman_row)
        
        for campo in CAMPOS_SOBRESCRIBIBLES:
            if campo in merged and campo in retell_row:
                if str(merged.get(campo, '')) != str(retell_row.get(campo, '')):
                    stats.fields_overwritten += 1
        
        for col in df_retell.columns:
            df_retell.at[call_id, col] = merged.get(col, df_retell.at[call_id, col])
    
    df_retell = df_retell.reset_index()
    
    return df_retell, stats


def generar_reporte_merge(stats: MergeStats) -> str:
    """
    Genera un reporte legible del proceso de merge.
    
    Args:
        stats: Estadísticas del merge
    
    Returns:
        String con el reporte
    """
    lines = [
        "",
        "=" * 50,
        "REPORTE DE MERGE RETELL + ROMAN",
        "=" * 50,
        f"Total registros Retell:    {stats.total_retell}",
        f"Total registros ROMAN:      {stats.total_roman}",
        f"Coincidencias (matched):    {stats.matched}",
        f"Solo en Retell:             {stats.unmatched_retell}",
        f"Solo en ROMAN (descartados): {stats.unmatched_roman}",
        f"Campos sobrescritos:        {stats.fields_overwritten}",
    ]
    
    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("TEST: Merge de datos")
    print("=" * 70)
    
    df_retell = pd.DataFrame({
        'call_id': ['call_001', 'call_002', 'call_003'],
        'msisdn': ['598912345678', '598912345679', '598912345680'],
        'customer_id': ['CLAROUY-0000001', 'CLAROUY-0000002', 'CLAROUY-0000003'],
        'encuesta_completada': [True, True, False],
        'motivo_cierre': ['', 'OK_RECHAZO_CLIENTE', ''],
        'global_experience': ['MUY_BUENA', '', '']
    })
    
    df_roman = pd.DataFrame({
        'call_id': ['call_001', 'call_002'],
        'encuesta_completada': [True, True],
        'motivo_cierre': ['OK_RECHAZO_CLIENTE', 'OK_RECHAZO_CLIENTE'],
        'global_experience': ['MUY_BUENA', 'PODRIA_MEJORAR'],
        'categoria': ['COBERTURA_SERVICIO', 'PORTABILIDAD']
    })
    
    df_merge, stats = merge_datos_inteligente(df_retell, df_roman)
    
    print(generar_reporte_merge(stats))
    print("\nDataFrame mergeado:")
    print(df_merge)
