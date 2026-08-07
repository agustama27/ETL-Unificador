"""
Procesador de archivo LOGCALL para integración en el pipeline CRM Bancor.

Filtra los registros con resultado CONTESTADOR/OCUPADO/NO RESPONDE/NO LLAMA,
cruza por RECNUMBER con el DataFrame ROMAN (posición 1-indexed) para obtener
el CUIT, y retorna registros ya en el formato CRM de 13 columnas.
"""
import pandas as pd
from pathlib import Path
from typing import Any

# Códigos de resultado LOGCALL que mapean a E0005 (Sin Contacto con Titular)
RESULTADOS_LOGCALL_E0005: dict[str, str] = {
    '1004': 'CONTESTADOR',
    '7': 'OCUPADO',
    '8': 'NO RESPONDE',
    '9': 'NO LLAMA',
}

_COLUMNAS_CUIT_ROMAN = ['id_cuil', '[Entrada] id_cuil', 'CUIL', '[Entrada] CUIL', 'Cuil', 'CUIT', 'Cuit', 'id_cuit']


def _leer_logcall(path_logcall: Path) -> pd.DataFrame:
    for encoding in ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1']:
        for sep in [';', ',']:
            try:
                df = pd.read_csv(
                    path_logcall, sep=sep, encoding=encoding,
                    quotechar='"', dtype=str,
                )
                df.columns = df.columns.str.strip()
                if 'RESULT' in df.columns and 'RECNUMBER' in df.columns:
                    return df
            except Exception:
                continue
    raise ValueError(f"No se pudo leer el archivo LOGCALL: {path_logcall}")


def _normalizar_cuit(valor: Any) -> str:
    if valor is None:
        return ''
    s = str(valor).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return ''.join(c for c in s if c.isdigit())


def _buscar_columna_cuit(df_roman: pd.DataFrame) -> str | None:
    for col in _COLUMNAS_CUIT_ROMAN:
        if col in df_roman.columns:
            return col
    return None


def procesar_logcall(
    path_logcall: Path,
    df_roman: pd.DataFrame,
    nombre_estudio: str,
    cuil_ya_procesados: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Procesa el archivo LOGCALL y retorna registros en el formato CRM de 13 columnas.

    - Estado fijo: E0005 (Sin Contacto con Titular)
    - Sub-Estado: vacío
    - CUIT: cruzado por RECNUMBER (posición 1-based en df_roman)
    - Descripción: texto del resultado (CONTESTADOR, OCUPADO, NO RESPONDE, NO LLAMA)
    - Responsable: código del estudio recibido por parámetro
    - Los CUITs en `cuil_ya_procesados` se omiten para evitar duplicados

    Args:
        path_logcall: Ruta al CSV del LOGCALL
        df_roman: DataFrame del ROMAN (sin filtros, con header en fila 0)
        nombre_estudio: Nombre del estudio para el campo Responsable
        cuil_ya_procesados: CUITs ya presentes en la salida (se actualiza in-place)

    Returns:
        (registros, logs)
    """
    from config_catalogos import CLASE_OPERACION, RESPONSABLES

    logs: list[str] = []
    if cuil_ya_procesados is None:
        cuil_ya_procesados = set()

    df = _leer_logcall(path_logcall)
    logs.append(f"Registros totales LOGCALL: {len(df)}")

    df['RESULT'] = df['RESULT'].str.strip()
    df_filtrado = df[df['RESULT'].isin(RESULTADOS_LOGCALL_E0005)].copy()
    logs.append(f"Con resultado E0005 (1004/7/8/9): {len(df_filtrado)}")

    if df_filtrado.empty:
        return [], logs

    df_filtrado['RECNUMBER'] = pd.to_numeric(
        df_filtrado['RECNUMBER'].str.strip(), errors='coerce'
    )
    df_filtrado = df_filtrado.dropna(subset=['RECNUMBER'])
    df_filtrado['RECNUMBER'] = df_filtrado['RECNUMBER'].astype(int)
    df_filtrado = df_filtrado.drop_duplicates(subset=['RECNUMBER'], keep='first')
    logs.append(f"Únicos por RECNUMBER: {len(df_filtrado)}")

    columna_cuit = _buscar_columna_cuit(df_roman)
    if not columna_cuit:
        logs.append("ADVERTENCIA: No se encontró columna CUIT en ROMAN. Sin registros LOGCALL.")
        return [], logs

    nombre_estudio_upper = nombre_estudio.upper().strip()
    codigo_responsable = RESPONSABLES.get(nombre_estudio_upper, '')
    if not codigo_responsable:
        for nombre, codigo in RESPONSABLES.items():
            if nombre_estudio_upper in nombre or nombre in nombre_estudio_upper:
                codigo_responsable = codigo
                break

    registros: list[dict[str, Any]] = []
    sin_cuit = 0
    duplicados = 0
    fuera_de_rango = 0

    for _, fila in df_filtrado.iterrows():
        recnumber = int(fila['RECNUMBER'])

        if recnumber < 1 or recnumber > len(df_roman):
            fuera_de_rango += 1
            continue

        roman_row = df_roman.iloc[recnumber - 1]
        cuit = _normalizar_cuit(roman_row.get(columna_cuit))

        if not cuit:
            sin_cuit += 1
            continue

        if cuit in cuil_ya_procesados:
            duplicados += 1
            continue

        resultado_desc = RESULTADOS_LOGCALL_E0005[fila['RESULT']]

        registros.append({
            'Clase de Operación': CLASE_OPERACION,
            'Estado': 'E0005',
            'Sub- Estado': '',
            'CUIT': cuit,
            'Cuenta': '',
            'Desc. Acuerdo Comercial': '',
            'Acuerdo Comercial': '',
            'Responsable': codigo_responsable,
            'Descripción': resultado_desc,
            'Persona de Contacto': '',
            'Juzgado': '',
            'Garante': '',
            'Notas': '',
        })
        cuil_ya_procesados.add(cuit)

    if fuera_de_rango:
        logs.append(f"RECNUMBER fuera de rango ROMAN: {fuera_de_rango}")
    if sin_cuit:
        logs.append(f"Sin CUIT en ROMAN: {sin_cuit}")
    if duplicados:
        logs.append(f"Duplicados omitidos (CUIT ya en salida): {duplicados}")
    logs.append(f"Registros LOGCALL incorporados: {len(registros)}")

    return registros, logs
