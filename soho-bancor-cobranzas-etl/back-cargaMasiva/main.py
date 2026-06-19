"""
Script principal para generar archivo de carga masiva al CRM Bancor

Flujo:
1. Lee CSV de calls/ con Call IDs (o usa datos de back-resultados)
2. Consulta API Retell.ai para cada llamada
3. Opcionalmente mergea con datos de ROMAN (roman/)
4. Mapea datos al formato CRM (13 columnas)
5. Valida cada registro
6. Genera archivo XLSX en output/

Variables de entorno:
- RETELL_API_KEY: Clave API de Retell.ai (requerida)
- USE_RETELL: Habilita consulta a Retell.ai (default: true)
- USE_ROMAN: Habilita integración con ROMAN (default: true)
- ROMAN_ONLY: Fuerza modo solo ROMAN (default: false)
- ESTUDIO: Nombre del estudio (default: EVOLTIS)
"""
import sys
import os
from pathlib import Path
from datetime import datetime

import pandas as pd

# Agregar el directorio procesos al path para importar los módulos propios
procesos_dir = Path(__file__).parent / "procesos"
sys.path.insert(0, str(procesos_dir))

# Importar adaptadores locales (usan carpetas de back-cargaMasiva)
from local_adapters import (
    obtener_datos_llamadas_retell_local as obtener_datos_llamadas_retell,
    obtener_datos_roman_local as obtener_datos_roman,
    obtener_df_roman_raw_local,
    merge_datos_inteligente,
    generar_reporte_merge,
)

# Importar módulos propios de carga masiva
from mapeador import mapear_todos_los_registros, obtener_resumen_mapeo
from logcall_manager import procesar_logcall
from validador import validar_registro
from excel_generator import (
    crear_excel_carga_masiva,
    crear_csv_carga_masiva,
    generar_resumen_validacion
)


def verificar_dia_carga() -> bool:
    """
    Verifica si hoy es día de carga (Miércoles o Viernes).

    Returns:
        True si es día de carga, False si no lo es
    """
    dia_semana = datetime.now().weekday()
    # Miércoles = 2, Viernes = 4
    return dia_semana in [2, 4]


def _normalizar_valor(valor):
    """Normaliza nulos de pandas a string vacío."""
    if pd.isna(valor):
        return ''
    return str(valor).strip()


def _parsear_bool_env(valor: str | None, default: bool = False) -> bool:
    """Parsea un bool desde variable de entorno."""
    if valor is None:
        return default
    return valor.strip().lower() in ['true', '1', 'yes', 'si']


def _hay_archivos_retell_en_calls() -> bool:
    """Indica si hay archivos CSV de Retell disponibles en calls/."""
    carpeta_calls = Path(__file__).parent / "calls"
    if not carpeta_calls.exists():
        return False
    return any(carpeta_calls.glob("*.csv"))


def cargar_datos_roman_sin_retell() -> dict:
    """Carga ROMAN desde CSV local en modo sin Retell."""
    carpeta_roman = Path(__file__).parent / "roman"
    archivos_csv = list(carpeta_roman.glob("*.csv"))

    if not archivos_csv:
        return {}

    archivo_roman = max(archivos_csv, key=lambda x: x.stat().st_mtime)

    df = None
    ultimo_error = None
    for encoding in ['latin-1', 'iso-8859-1', 'cp1252', 'utf-8', 'utf-16']:
        for separador in [',', ';']:
            try:
                df = pd.read_csv(archivo_roman, encoding=encoding, sep=separador)
                break
            except Exception as e:
                ultimo_error = e
        if df is not None:
            break

    if df is None:
        raise ValueError(f"No se pudo leer CSV ROMAN en modo sin Retell: {ultimo_error}")

    df.columns = df.columns.str.strip()
    columna_call_id = None
    for candidata in ['ID de Llamada', 'Call ID', 'call_id']:
        if candidata in df.columns:
            columna_call_id = candidata
            break

    if not columna_call_id:
        raise ValueError(
            "No se encontro columna de call_id en ROMAN. "
            "Se esperaba una de: ID de Llamada, Call ID, call_id"
        )

    datos_roman = {}
    for _, fila in df.iterrows():
        call_id = _normalizar_valor(fila.get(columna_call_id))
        if not call_id:
            continue

        def _extraer_cuit(val):
            v = _normalizar_valor(val)
            if v.endswith('.0'):
                v = v[:-2]
            return ''.join(c for c in v if c.isdigit())

        cuil = (
            _extraer_cuit(fila.get('[Entrada] CUIL'))
            or _extraer_cuit(fila.get('[Entrada] id_cuil'))
            or _extraer_cuit(fila.get('CUIL'))
        )
        variables_dinamicas = {
            'CUIL': cuil,
            'Cuenta': _normalizar_valor(fila.get('[Entrada] Cuenta', fila.get('Cuenta'))),
        }

        postcall = {
            'ESTADO': _normalizar_valor(fila.get('[Salida] ESTADO', fila.get('ESTADO'))),
            'SUBESTADO': _normalizar_valor(fila.get('[Salida] SUBESTADO', fila.get('SUBESTADO'))),
            'OBSERVACIONES': _normalizar_valor(
                fila.get('[Salida] OBSERVACIONES', fila.get('OBSERVACIONES'))
            ),
            'Comentarios': _normalizar_valor(
                fila.get('[Salida] Comentarios', fila.get('Comentarios'))
            ),
        }

        datos_roman[call_id] = {
            'variables_dinamicas': variables_dinamicas,
            'postcall': postcall,
        }

    return datos_roman


def main():
    """Función principal que ejecuta el flujo completo."""
    print("\n" + "=" * 70)
    print("GENERADOR DE CARGA MASIVA - CRM BANCOR")
    print("=" * 70)

    # Leer configuración desde variables de entorno
    use_retell_env = os.getenv('USE_RETELL')
    retell_detectado = _hay_archivos_retell_en_calls()
    usar_retell = _parsear_bool_env(use_retell_env, default=retell_detectado)
    usar_roman = _parsear_bool_env(os.getenv('USE_ROMAN'), default=True)
    modo_solo_roman = _parsear_bool_env(os.getenv('ROMAN_ONLY'), default=False)
    nombre_estudio = os.getenv('ESTUDIO', 'EVOLTIS')
    retell_forzado = use_retell_env is not None

    if modo_solo_roman:
        usar_retell = False
        usar_roman = True

    print(f"\nConfiguracion:")
    print(f"  - Estudio: {nombre_estudio}")
    print(f"  - Usar Retell: {'Si' if usar_retell else 'No'}")
    if not modo_solo_roman:
        if retell_forzado:
            print(f"  - USE_RETELL forzado por entorno: {use_retell_env}")
        else:
            print(
                "  - USE_RETELL no definido: "
                f"autodeteccion en calls/ -> {'Si' if retell_detectado else 'No'}"
            )
    print(f"  - Usar ROMAN: {'Si' if usar_roman else 'No'}")
    if modo_solo_roman:
        print("  - Modo solo ROMAN: Si")

    if not usar_retell and not usar_roman:
        print("\nERROR: Configuracion invalida. Debe habilitar Retell, ROMAN o ambos.")
        return 1

    # Verificar día de carga
    if not verificar_dia_carga():
        print("\nADVERTENCIA: Hoy NO es dia de carga (Miercoles o Viernes)")
        print("  Los archivos se cargan los Miercoles y Viernes antes de 12:30 hrs")
        print("  Email destino: Mora_Prejudicial_Estudios@bancor.com.ar")

    datos_retell = {}

    # Paso 1: Obtener datos de Retell
    if usar_retell:
        print("\n" + "-" * 50)
        print("[1/5] Obteniendo datos de Retell.ai...")
        print("-" * 50)

        try:
            datos_retell = obtener_datos_llamadas_retell()
        except Exception as e:
            print(f"ERROR al obtener datos de Retell: {str(e)}")
            return 1

        if not datos_retell:
            print("No se obtuvieron datos de Retell. Abortando.")
            return 1

        print(f"  - Llamadas obtenidas: {len(datos_retell)}")
    else:
        print("\n" + "-" * 50)
        print("[1/5] Retell deshabilitado por configuracion")
        print("-" * 50)

    # Paso 2: Obtener y mergear datos de ROMAN
    datos_finales = datos_retell

    if usar_roman:
        print("\n" + "-" * 50)
        print("[2/5] Buscando datos de ROMAN...")
        print("-" * 50)

        try:
            datos_roman = obtener_datos_roman()

            if datos_roman:
                print(f"  - Registros ROMAN encontrados: {len(datos_roman)}")
                if usar_retell:
                    print("\n  Aplicando merge inteligente...")

                    datos_finales, stats = merge_datos_inteligente(
                        datos_retell=datos_retell,
                        datos_roman=datos_roman
                    )
                    print(generar_reporte_merge(stats))
                else:
                    datos_finales = datos_roman
                    print("  - Modo sin Retell: usando ROMAN como fuente principal")
            else:
                print("  - No se encontro archivo ROMAN o esta vacio")
                if usar_retell:
                    print("  - Continuando solo con datos de Retell")
                else:
                    print("No se obtuvieron datos de ROMAN. Abortando.")
                    return 1
        except Exception as e:
            print(f"  ADVERTENCIA - Error al procesar ROMAN: {str(e)}")
            if usar_retell:
                print("  - Continuando solo con datos de Retell")
            else:
                print("  - Intentando carga ROMAN directa sin Retell...")
                try:
                    datos_finales = cargar_datos_roman_sin_retell()
                    print(f"  - Registros ROMAN cargados (modo directo): {len(datos_finales)}")
                    if not datos_finales:
                        print("No se obtuvieron datos de ROMAN. Abortando.")
                        return 1
                except Exception as e2:
                    print(f"ERROR en carga ROMAN directa: {str(e2)}")
                    return 1
    else:
        if usar_retell:
            print("\n[2/5] ROMAN deshabilitado, usando solo datos de Retell")
        else:
            print("\n[2/5] ROMAN deshabilitado")

    # Paso 3: Mapear al formato CRM
    print("\n" + "-" * 50)
    print(f"[3/5] Mapeando {len(datos_finales)} registros al formato CRM...")
    print("-" * 50)

    registros_mapeados = mapear_todos_los_registros(datos_finales, nombre_estudio)

    if not registros_mapeados:
        print("No hay registros con estado valido para procesar. Abortando.")
        return 1

    # Mostrar resumen por estado (antes de LOGCALL)
    resumen = obtener_resumen_mapeo(registros_mapeados)
    print("\n  Distribucion por estado (Retell/ROMAN):")
    for estado, cantidad in sorted(resumen.items()):
        print(f"    {estado}: {cantidad}")

    # Paso 3.5: Integrar LOGCALL
    carpeta_logcall = Path(__file__).parent / "logcall"
    archivos_logcall = list(carpeta_logcall.glob("*.csv")) if carpeta_logcall.exists() else []

    if archivos_logcall:
        print("\n" + "-" * 50)
        print(f"[3.5/5] Integrando LOGCALL ({len(archivos_logcall)} archivo/s)...")
        print("-" * 50)

        df_roman_raw = obtener_df_roman_raw_local()

        if df_roman_raw is None:
            print("  ADVERTENCIA: No se pudo cargar ROMAN para cruce LOGCALL. Paso omitido.")
        else:
            cuil_en_salida = {r['CUIT'] for r in registros_mapeados if r.get('CUIT')}
            total_logcall_nuevos = 0

            for archivo_logcall in archivos_logcall:
                print(f"  Procesando: {archivo_logcall.name}")
                registros_logcall, logs_logcall = procesar_logcall(
                    archivo_logcall, df_roman_raw, nombre_estudio, cuil_en_salida
                )
                for linea in logs_logcall:
                    print(f"    {linea}")
                registros_mapeados.extend(registros_logcall)
                total_logcall_nuevos += len(registros_logcall)

            print(f"\n  Total registros LOGCALL incorporados: {total_logcall_nuevos}")
            print(f"  Total registros tras LOGCALL: {len(registros_mapeados)}")

    # Paso 4: Validar registros
    print("\n" + "-" * 50)
    print("[4/5] Validando registros...")
    print("-" * 50)

    registros_validos = []
    todos_errores = []

    for i, registro in enumerate(registros_mapeados):
        es_valido, reg_normalizado, errores = validar_registro(registro)

        if es_valido:
            registros_validos.append(reg_normalizado)
        else:
            # Agregar info del registro al error
            cuit = registro.get('CUIT', 'SIN_CUIT')
            for error in errores:
                todos_errores.append(f"[CUIT: {cuit}] {error}")

    # Mostrar resumen de validación
    print(generar_resumen_validacion(
        total_procesados=len(registros_mapeados),
        total_validos=len(registros_validos),
        total_errores=len(todos_errores),
        errores_detalle=todos_errores
    ))

    if not registros_validos:
        print("\nERROR: No hay registros validos para generar el archivo.")
        return 1

    # Paso 5: Generar Excel y CSV
    print("\n" + "-" * 50)
    print("[5/5] Generando archivos Excel y CSV...")
    print("-" * 50)

    carpeta_output = Path(__file__).parent / "output"

    try:
        ruta_excel = crear_excel_carga_masiva(
            registros=registros_validos,
            nombre_estudio=nombre_estudio,
            carpeta_salida=carpeta_output
        )
        print(f"  [OK] Excel generado: {ruta_excel.name}")

        ruta_csv = crear_csv_carga_masiva(
            registros=registros_validos,
            nombre_estudio=nombre_estudio,
            carpeta_salida=carpeta_output
        )
        print(f"  [OK] CSV generado: {ruta_csv.name}")
    except Exception as e:
        print(f"ERROR al generar archivos: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    # Resumen final
    print("\n" + "=" * 70)
    print("PROCESO COMPLETADO EXITOSAMENTE")
    print("=" * 70)
    print(f"\n  Archivos generados:")
    print(f"    - Excel: {ruta_excel.name}")
    print(f"    - CSV:   {ruta_csv.name}")
    print(f"  Total de registros: {len(registros_validos)}")
    print(f"\n  Instrucciones de envio:")
    print(f"    - Dias de carga: Miercoles y Viernes")
    print(f"    - Horario limite: 12:30 hrs")
    print(f"    - Email: Mora_Prejudicial_Estudios@bancor.com.ar")
    print(f"    - Asunto: Cargas masivas CRM ({datetime.now().strftime('%d/%m/%Y')}) {nombre_estudio}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nADVERTENCIA - Proceso interrumpido por el usuario")
        sys.exit(130)
    except Exception as e:
        print("\n" + "=" * 70)
        print("ERROR EN EL PROCESO")
        print("=" * 70)
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
