import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import sys

# Importar la función del módulo retell_manager
# Agregar el directorio padre al path para importar retell_manager
sys.path.insert(0, str(Path(__file__).parent))

from retell_manager import obtener_datos_llamadas_retell
from roman_manager import obtener_datos_roman
from data_merger import merge_datos_inteligente, generar_reporte_merge


def aplanar_diccionario(diccionario: Dict[str, Any], prefijo: str = '') -> Dict[str, Any]:
    """
    Aplana un diccionario anidado en un diccionario plano.
    
    Args:
        diccionario: Diccionario a aplanar
        prefijo: Prefijo para las claves (para distinguir variables_dinamicas de postcall)
        
    Returns:
        Diccionario plano con las claves aplanadas
    """
    resultado = {}
    
    if not isinstance(diccionario, dict):
        return resultado
    
    for clave, valor in diccionario.items():
        nueva_clave = f"{prefijo}_{clave}" if prefijo else clave
        
        # Si el valor es otro diccionario, aplanarlo recursivamente
        if isinstance(valor, dict):
            resultado_anidado = aplanar_diccionario(valor, nueva_clave)
            resultado.update(resultado_anidado)
        # Si el valor es una lista, convertirla a string
        elif isinstance(valor, list):
            resultado[nueva_clave] = str(valor) if valor else ''
        # Si el valor es None, usar string vacío
        elif valor is None:
            resultado[nueva_clave] = ''
        # Para otros tipos, convertir a string
        else:
            resultado[nueva_clave] = str(valor)
    
    return resultado


def generar_csv_gestiones(usar_roman: bool = True) -> Path:
    """
    Genera un CSV con las gestiones obtenidas de Retell.ai,
    opcionalmente enriquecidas con datos de ROMAN.

    Cada fila corresponde a una llamada y las columnas son las variables
    dinámicas y postcall obtenidas.

    Args:
        usar_roman: Si True, intenta cargar y mergear datos de ROMAN (default: True)

    Returns:
        Ruta del archivo CSV generado
    """
    print("=" * 60)
    print("Generador de CSV de Gestiones Bancor")
    print("=" * 60)
    
    # Obtener datos de las llamadas desde Retell
    print("\nObteniendo datos de las llamadas desde Retell.ai...")
    datos_llamadas = obtener_datos_llamadas_retell()

    if not datos_llamadas:
        print("No se obtuvieron datos de llamadas. No se generará ningún archivo.")
        return None

    # Intentar integrar datos de ROMAN si está habilitado
    if usar_roman:
        print("\n" + "=" * 60)
        print("BUSCANDO DATOS DE ROMAN...")
        print("=" * 60)

        datos_roman = obtener_datos_roman()

        if datos_roman:
            print(f"OK - Encontrados {len(datos_roman)} registros en ROMAN")
            print("\nAplicando merge inteligente entre Retell y ROMAN...")

            try:
                datos_llamadas, stats = merge_datos_inteligente(
                    datos_retell=datos_llamadas,
                    datos_roman=datos_roman
                )

                # Mostrar reporte de merge
                print("\n" + generar_reporte_merge(stats))

            except Exception as e:
                print(f"\nADVERTENCIA - Error al aplicar merge con ROMAN: {str(e)}")
                print("Continuando con datos de Retell unicamente...")
        else:
            print("OK - No se encontro archivo ROMAN o esta vacio")
            print("Continuando con datos de Retell unicamente...")

    print(f"\nProcesando {len(datos_llamadas)} llamadas para generar el CSV...")
    
    # Preparar lista de filas para el DataFrame
    filas = []
    
    for call_id, datos_llamada in datos_llamadas.items():
        # Crear diccionario base con el call_id
        fila = {'call_id': call_id}
        
        # Aplanar variables dinámicas
        variables_dinamicas = datos_llamada.get('variables_dinamicas', {})
        if variables_dinamicas:
            variables_aplanadas = aplanar_diccionario(variables_dinamicas, 'var')
            fila.update(variables_aplanadas)
        
        # Aplanar datos postcall
        postcall = datos_llamada.get('postcall', {})
        if postcall:
            postcall_aplanado = aplanar_diccionario(postcall, 'postcall')
            fila.update(postcall_aplanado)
        
        filas.append(fila)
    
    # Crear DataFrame
    df = pd.DataFrame(filas)
    
    # Si no hay datos, retornar None
    if df.empty:
        print("No hay datos para generar el CSV.")
        return None
    
    # Definir las 28 columnas fijas que debe tener el CSV (formato estándar)
    COLUMNAS_FIJAS = [
        'call_id',
        'AgrupadorProducto',
        'CUIL',
        'ClienteNombre',
        'Cliente_BT',
        'Cuenta',
        'Dias_Mora',
        'IVAInteresAdeudado',
        'InteresAdeudado',
        'Mail',
        'MontoAdeudado',
        'NumeroOperacion',
        'OFERTA_Importe',
        'SaldoCapital',
        'Sucursal_Cuenta',
        'fecha_hoy',
        'fecha_limite_sistema',
        'fecha_manana',
        'hora_actual',
        'user_number',
        'Comentarios',
        'DESCRIPCION',
        'ESTADO',
        'Email_valido',
        'Fecha_compromiso',
        'Monto_compromiso',
        'SUBESTADO',
        'compromiso_de_pago_logrado'
    ]

    # Obtener todas las columnas únicas de todas las filas
    # (puede que algunas llamadas tengan diferentes variables)
    todas_las_columnas = set()
    for fila in filas:
        todas_las_columnas.update(fila.keys())

    # Reordenar columnas: call_id primero, luego variables dinámicas, luego postcall
    columnas_ordenadas = ['call_id']
    columnas_ordenadas.extend(sorted([c for c in todas_las_columnas if c.startswith('var_')]))
    columnas_ordenadas.extend(sorted([c for c in todas_las_columnas if c.startswith('postcall_')]))
    columnas_ordenadas.extend(sorted([c for c in todas_las_columnas if c not in columnas_ordenadas]))

    # Reordenar el DataFrame con todas las columnas posibles
    for col in columnas_ordenadas:
        if col not in df.columns:
            df[col] = ''

    df = df[columnas_ordenadas]

    # Reemplazar NaN por strings vacíos
    df = df.fillna('')

    # Contar columnas antes de renombrar (para el mensaje informativo)
    num_variables_dinamicas = len([c for c in df.columns if c.startswith('var_')])
    num_postcall = len([c for c in df.columns if c.startswith('postcall_')])

    # Renombrar columnas eliminando los prefijos "var_" y "postcall_"
    nuevo_nombre_columnas = {}
    for col in df.columns:
        if col == 'call_id':
            nuevo_nombre_columnas[col] = col
        elif col.startswith('var_'):
            # Eliminar el prefijo "var_"
            nuevo_nombre_columnas[col] = col[4:]  # Remover "var_"
        elif col.startswith('postcall_'):
            # Eliminar el prefijo "postcall_"
            nuevo_nombre_columnas[col] = col[9:]  # Remover "postcall_"
        else:
            nuevo_nombre_columnas[col] = col

    df = df.rename(columns=nuevo_nombre_columnas)

    # Excluir columnas que no están en la lista de columnas fijas
    columnas_extra = [col for col in df.columns if col not in COLUMNAS_FIJAS]

    if columnas_extra:
        print(f"\nColumnas excluidas (no están en formato estándar): {', '.join(columnas_extra)}")

    # Asegurar que todas las columnas fijas existan (rellenar con vacío si no existen)
    for col in COLUMNAS_FIJAS:
        if col not in df.columns:
            df[col] = ''

    # Reordenar DataFrame para que tenga exactamente las 28 columnas fijas en el orden correcto
    df = df[COLUMNAS_FIJAS]
    
    # Obtener ruta de la carpeta results
    base_dir = Path(__file__).parent.parent
    carpeta_results = base_dir / "results"
    
    # Crear carpeta si no existe
    carpeta_results.mkdir(exist_ok=True)
    
    # Generar nombre del archivo con formato DDMMAAAA
    fecha_actual = datetime.now()
    nombre_archivo = f"gestiones_bancor_{fecha_actual.strftime('%d%m%Y')}.csv"
    ruta_archivo = carpeta_results / nombre_archivo
    
    # Guardar CSV con separador punto y coma (formato europeo)
    df.to_csv(ruta_archivo, sep=';', index=False, encoding='utf-8')
    
    print(f"\nOK - CSV generado exitosamente:")
    print(f"  Archivo: {ruta_archivo}")
    print(f"  Total de llamadas: {len(df)}")
    print(f"  Total de columnas: {len(df.columns)} (formato fijo)")
    print(f"\nColumnas en formato estándar (28 columnas):")
    print(f"  - Identificador y datos del cliente: 20 columnas")
    print(f"  - Tipificación y gestión: 8 columnas")
    
    return ruta_archivo


if __name__ == "__main__":
    try:
        ruta_archivo = generar_csv_gestiones()
        if ruta_archivo:
            print(f"\n✓ Proceso completado exitosamente")
        else:
            print(f"\nADVERTENCIA - No se genero ningun archivo")
            sys.exit(1)
    except Exception as e:
        print(f"\nERROR - Error al generar el CSV: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

