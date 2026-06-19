from pathlib import Path
from procesos.base_generator import procesar_base, procesar_base_completa
from procesos.phone_extractor import extraer_telefonos

if __name__ == "__main__":
    base_dir = Path(__file__).parent

    print("\n" + "=" * 70)
    print("PROCESAMIENTO DE BASE DE CLIENTES BANCOR")
    print("=" * 70)

    # Paso 1: Procesar la base de clientes (con filtros)
    print("\n[PASO 1/4] Procesando base de clientes (con filtros)...")
    procesar_base()

    # Paso 2: Procesar la base completa (sin filtros, con Estado Cuenta y Tasa_40)
    print("\n" + "=" * 70)
    print("[PASO 2/4] Procesando base completa (sin filtros)...")
    print("=" * 70)
    try:
        procesar_base_completa()
        print(f"\nProcesamiento de base completa finalizado exitosamente")
    except Exception as e:
        print(f"\nError al procesar base completa: {str(e)}")
        import traceback
        traceback.print_exc()

    # Paso 3: Extraer teléfonos de la base con filtros
    print("\n" + "=" * 70)
    print("[PASO 3/4] Extrayendo teléfonos por cliente (con filtros)...")
    print("=" * 70)
    try:
        carpeta_con_filtros = base_dir / "base-generada" / "con-filtros"
        ruta_telefonos = extraer_telefonos(carpeta_generada=carpeta_con_filtros, nombre_base="base_bancor")
        if ruta_telefonos:
            print(f"\nExtraccion de telefonos completada exitosamente")
        else:
            print(f"\nAdvertencia: No se genero el archivo de telefonos")
    except Exception as e:
        print(f"\nError al extraer telefonos: {str(e)}")
        import traceback
        traceback.print_exc()

    # Paso 4: Extraer teléfonos de la base sin filtros
    print("\n" + "=" * 70)
    print("[PASO 4/4] Extrayendo teléfonos por cliente (sin filtros)...")
    print("=" * 70)
    try:
        carpeta_sin_filtros = base_dir / "base-generada" / "sin-filtros"
        ruta_telefonos = extraer_telefonos(
            carpeta_generada=carpeta_sin_filtros,
            nombre_base="BANCOR_ROMAN",
            formato_fecha="%Y%m%d",
            prefijo_salida="BANCOR_E1KIA",
            sufijo_salida="sinestrategia",
            columnas_salida_snake_case=True,
        )
        if ruta_telefonos:
            print(f"\nExtraccion de telefonos completada exitosamente")
        else:
            print(f"\nAdvertencia: No se genero el archivo de telefonos")
    except Exception as e:
        print(f"\nError al extraer telefonos: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("PROCESO COMPLETADO")
    print("=" * 70)
