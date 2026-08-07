import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd


CODIFICACIONES = ['latin-1', 'iso-8859-1', 'cp1252', 'utf-8', 'utf-16']
MARCADORES_VACIOS = {'', 'nan', 'none', 'nat', 'null'}
PALABRAS_TELEFONO = ('telefono', 'celular', 'phone', 'movil', 'mobile', 'whatsapp')
COLUMNAS_SALIDA = (
    'numero_referencia',
    'equivalencias_normalizadas',
    'apariciones_source',
    'ejemplo_valor_original',
    'columna_origen_ejemplo',
    'fila_origen_ejemplo',
)


def leer_csv_con_codificacion(archivo_csv, separador=';'):
    """Lee un CSV con cadena de codificaciones y fallback con errors='replace'."""
    for encoding in CODIFICACIONES:
        try:
            df = pd.read_csv(
                archivo_csv,
                sep=separador,
                encoding=encoding,
                low_memory=False,
                dtype=str,
            )
            return df, encoding
        except UnicodeDecodeError:
            continue

    with open(archivo_csv, 'r', encoding='latin-1', errors='replace') as archivo:
        df = pd.read_csv(archivo, sep=separador, low_memory=False, dtype=str)
    return df, 'latin-1(errors=replace)'


def normalizar_texto(valor):
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return ''.join(c for c in texto if c.isalnum())


def es_columna_telefono(nombre_columna):
    normalizada = normalizar_texto(nombre_columna)
    if normalizada.startswith('tel'):
        return True
    return any(palabra in normalizada for palabra in PALABRAS_TELEFONO)


def inferir_columnas_telefono(df):
    return [col for col in df.columns if es_columna_telefono(col)]


def parsear_columnas_explicitas(columnas_raw):
    if not columnas_raw:
        return []
    columnas = [col.strip() for col in str(columnas_raw).split(',') if col.strip()]
    return columnas


def resolver_columnas(df, columnas_raw, etiqueta_dataset):
    columnas_explicitas = parsear_columnas_explicitas(columnas_raw)
    if columnas_explicitas:
        faltantes = [col for col in columnas_explicitas if col not in df.columns]
        if faltantes:
            raise ValueError(
                f"Columnas no encontradas en {etiqueta_dataset}: {faltantes}. "
                f"Columnas disponibles: {list(df.columns)}"
            )
        return columnas_explicitas, 'explicitas'

    columnas_inferidas = inferir_columnas_telefono(df)
    if not columnas_inferidas:
        raise ValueError(
            f"No se detectaron columnas de telefono en {etiqueta_dataset}. "
            "Use --source-column / --target-column para indicar columnas manualmente."
        )
    return columnas_inferidas, 'inferidas'


def limpiar_numero(valor):
    if pd.isna(valor):
        return ''

    texto = str(valor).strip()
    if texto.lower() in MARCADORES_VACIOS:
        return ''

    texto = re.sub(r'\.0$', '', texto)
    return re.sub(r'\D', '', texto)


def expandir_equivalencias(numero):
    equivalencias = {numero}
    if numero.startswith('549') and len(numero) > 3:
        equivalencias.add(numero[3:])
    elif numero.startswith('54') and len(numero) > 2:
        equivalencias.add(numero[2:])
    return {n for n in equivalencias if n}


def extraer_telefonos(df, columnas):
    telefonos = []
    for columna in columnas:
        serie = df[columna] if columna in df.columns else pd.Series(dtype=str)
        for row_index, valor in enumerate(serie.tolist(), start=2):
            numero = limpiar_numero(valor)
            if not numero:
                continue
            equivalencias = expandir_equivalencias(numero)
            telefonos.append(
                {
                    'row_index': row_index,
                    'column': columna,
                    'raw_value': str(valor),
                    'digits': numero,
                    'equivalencias': equivalencias,
                }
            )
    return telefonos


def firma_equivalencias(equivalencias):
    return '|'.join(sorted(equivalencias))


def numero_referencia(equivalencias):
    return min(equivalencias, key=lambda x: (len(x), x))


def detectar_faltantes(source_telefonos, target_set):
    faltantes = []
    for telefono in source_telefonos:
        if telefono['equivalencias'].isdisjoint(target_set):
            faltantes.append(telefono)
    return faltantes


def agrupar_faltantes(faltantes):
    agrupados = {}
    for item in faltantes:
        firma = firma_equivalencias(item['equivalencias'])
        if firma not in agrupados:
            agrupados[firma] = {
                'numero_referencia': numero_referencia(item['equivalencias']),
                'equivalencias_normalizadas': firma,
                'apariciones_source': 0,
                'ejemplo_valor_original': item['raw_value'],
                'columna_origen_ejemplo': item['column'],
                'fila_origen_ejemplo': item['row_index'],
            }
        agrupados[firma]['apariciones_source'] += 1

    filas = list(agrupados.values())
    filas.sort(key=lambda x: (-x['apariciones_source'], x['numero_referencia']))
    return filas


def construir_parser():
    parser = argparse.ArgumentParser(
        description='Compara telefonos entre dos CSV y detecta faltantes del source en target.'
    )
    parser.add_argument('--source', required=True, help='CSV de origen (archivo 1).')
    parser.add_argument('--target', required=True, help='CSV objetivo (archivo 2).')
    parser.add_argument('--source-column', help='Columna(s) de telefono en source. Admite coma.')
    parser.add_argument('--target-column', help='Columna(s) de telefono en target. Admite coma.')
    parser.add_argument('--output', help='Ruta CSV de salida para telefonos faltantes.')
    return parser


def main(args=None):
    parser = construir_parser()
    parsed = parser.parse_args(args=args)

    source_path = Path(parsed.source)
    target_path = Path(parsed.target)

    if not source_path.exists():
        raise FileNotFoundError(f"No existe source: {source_path}")
    if not target_path.exists():
        raise FileNotFoundError(f"No existe target: {target_path}")

    print('=' * 72)
    print('COMPARADOR DE TELEFONOS ENTRE CSV')
    print('=' * 72)
    print(f"Source: {source_path}")
    print(f"Target: {target_path}")

    df_source, enc_source = leer_csv_con_codificacion(source_path)
    df_target, enc_target = leer_csv_con_codificacion(target_path)
    print(f"\nCodificacion source: {enc_source}")
    print(f"Codificacion target: {enc_target}")

    source_columns, source_mode = resolver_columnas(df_source, parsed.source_column, 'source')
    target_columns, target_mode = resolver_columnas(df_target, parsed.target_column, 'target')

    print(f"\nColumnas source ({source_mode}): {source_columns}")
    print(f"Columnas target ({target_mode}): {target_columns}")

    source_telefonos = extraer_telefonos(df_source, source_columns)
    target_telefonos = extraer_telefonos(df_target, target_columns)

    target_set = set()
    for item in target_telefonos:
        target_set.update(item['equivalencias'])

    faltantes = detectar_faltantes(source_telefonos, target_set)
    faltantes_agrupados = agrupar_faltantes(faltantes)

    source_unicos = {firma_equivalencias(item['equivalencias']) for item in source_telefonos}
    target_unicos = {firma_equivalencias(item['equivalencias']) for item in target_telefonos}

    print('\nResumen:')
    print(f"- Total source (apariciones): {len(source_telefonos)}")
    print(f"- Total target (apariciones): {len(target_telefonos)}")
    print(f"- Total source (equivalencias unicas): {len(source_unicos)}")
    print(f"- Total target (equivalencias unicas): {len(target_unicos)}")
    print(f"- Faltantes (apariciones source): {len(faltantes)}")
    print(f"- Faltantes (equivalencias unicas): {len(faltantes_agrupados)}")

    if faltantes_agrupados:
        print('\nEjemplos de faltantes (hasta 10):')
        for item in faltantes_agrupados[:10]:
            print(
                f"  - {item['numero_referencia']} "
                f"(apariciones: {item['apariciones_source']}, "
                f"columna: {item['columna_origen_ejemplo']}, "
                f"fila: {item['fila_origen_ejemplo']})"
            )
    else:
        print('\nNo se detectaron faltantes en source respecto a target.')

    if parsed.output:
        output_path = Path(parsed.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_out = pd.DataFrame.from_records(faltantes_agrupados)
        if df_out.empty:
            df_out = pd.DataFrame(columns=pd.Index(COLUMNAS_SALIDA))
        else:
            df_out = df_out.reindex(columns=COLUMNAS_SALIDA)
        df_out.to_csv(output_path, sep=';', encoding='utf-8', index=False)
        print(f"\nArchivo de faltantes guardado en: {output_path}")

    return {
        'source_apariciones': len(source_telefonos),
        'target_apariciones': len(target_telefonos),
        'source_unicos': len(source_unicos),
        'target_unicos': len(target_unicos),
        'faltantes_apariciones': len(faltantes),
        'faltantes_unicos': len(faltantes_agrupados),
    }


if __name__ == '__main__':
    main()
