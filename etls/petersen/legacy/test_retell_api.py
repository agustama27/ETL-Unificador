"""Script de diagnóstico para probar la conexión con la API de Retell"""
import os
import sys
from dataclasses import replace
from pathlib import Path

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from procesos.retell_manager import (
    load_default_dotenv_locations,
    RetellClient,
    RetellAPIError,
    parse_call_path_templates,
    DEFAULT_RETELL_BASE_URL,
    DEFAULT_CALL_PATH_TEMPLATE,
    FALLBACK_CALL_PATH_TEMPLATES,
)

def test_retell_connection():
    """Prueba la conexión con la API de Retell usando un call ID de prueba"""
    
    # Cargar variables de entorno
    load_default_dotenv_locations(override=False)
    
    api_key = os.getenv("RETELL_API_KEY", "").strip()
    if not api_key:
        print("❌ ERROR: RETELL_API_KEY no encontrada en variables de entorno")
        print("   Verifica que el archivo .env exista y contenga RETELL_API_KEY=...")
        return False
    
    print(f"✅ API Key encontrada: {api_key[:20]}...{api_key[-5:]}")
    print(f"   Longitud de API Key: {len(api_key)} caracteres")
    
    # Verificar si la API key parece incompleta
    if len(api_key) < 30:
        print(f"   ⚠️  ADVERTENCIA: La API Key parece muy corta. Normalmente son más largas.")
    
    # Obtener un call ID del CSV
    retell_dir = Path(__file__).parent / "retell"
    csv_files = list(retell_dir.glob("export_*.csv"))
    
    if not csv_files:
        print("❌ ERROR: No se encontró ningún CSV en la carpeta retell/")
        return False
    
    latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
    print(f"✅ CSV encontrado: {latest_csv.name}")
    
    # Leer el primer call ID del CSV
    import csv
    with latest_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        call_ids = [row.get("Call ID", "").strip() for row in reader if row.get("Call ID", "").strip()]
    
    if not call_ids:
        print("❌ ERROR: No se encontraron Call IDs en el CSV")
        return False
    
    test_call_id = call_ids[0]
    print(f"✅ Call ID de prueba: {test_call_id}")
    
    # Configurar cliente
    base_url = os.getenv("RETELL_BASE_URL", DEFAULT_RETELL_BASE_URL).strip() or DEFAULT_RETELL_BASE_URL
    auth_header = os.getenv("RETELL_AUTH_HEADER", "Authorization").strip() or "Authorization"
    auth_scheme = os.getenv("RETELL_AUTH_SCHEME", "Bearer")
    
    print(f"\n📋 Configuración:")
    print(f"   Base URL: {base_url}")
    print(f"   Auth Header: {auth_header}")
    print(f"   Auth Scheme: {auth_scheme}")
    
    client = RetellClient(
        api_key=api_key,
        base_url=base_url,
        call_path_template=DEFAULT_CALL_PATH_TEMPLATE,
        auth_header=auth_header,
        auth_scheme=auth_scheme,
    )
    
    # Mostrar headers que se enviarán
    headers = client._headers()
    print(f"\n🔐 Headers de autenticación:")
    print(f"   {auth_header}: {headers[auth_header][:30]}...")
    
    # Construir URL de prueba
    url = client._build_url(test_call_id)
    print(f"\n🔗 URL de prueba: {url}")
    
    # Probar con diferentes path templates
    path_templates = parse_call_path_templates(
        os.getenv("RETELL_CALL_PATH_TEMPLATE", DEFAULT_CALL_PATH_TEMPLATE)
    )
    
    print(f"\n🔄 Probando {len(path_templates)} path templates...")
    
    for i, template in enumerate(path_templates, 1):
        print(f"\n{'='*80}")
        print(f"[{i}/{len(path_templates)}] Probando: {template}")
        temp_client = replace(client, call_path_template=template)
        test_url = temp_client._build_url(test_call_id)
        print(f"   URL completa: {test_url}")
        
        try:
            response = temp_client.get_call(test_call_id, max_retries=1)
            print(f"\n   ✅ ✅ ✅ ÉXITO! Respuesta recibida ✅ ✅ ✅")
            print(f"   Keys en respuesta: {list(response.keys())[:10]}...")
            print(f"\n   📊 Primeros campos de la respuesta:")
            for key in list(response.keys())[:5]:
                value = response.get(key)
                if isinstance(value, dict):
                    print(f"      - {key}: {{dict con {len(value)} campos}}")
                elif isinstance(value, list):
                    print(f"      - {key}: [lista con {len(value)} elementos]")
                else:
                    value_str = str(value)[:50]
                    print(f"      - {key}: {value_str}")
            return True
        except RetellAPIError as e:
            print(f"\n   ❌ ERROR RetellAPIError:")
            print(f"      Mensaje: {str(e)}")
            if e.status_code:
                print(f"      Código HTTP: {e.status_code}")
            if e.body:
                print(f"      Cuerpo de respuesta: {e.body[:200]}")
            
            # Análisis específico por código de error
            if e.status_code == 401:
                print(f"\n      🔍 DIAGNÓSTICO 401:")
                print(f"         - La API Key es incorrecta o inválida")
                print(f"         - Verifica que la API Key esté completa en el archivo .env")
                print(f"         - Verifica que la API Key sea válida en tu cuenta de Retell")
            elif e.status_code == 403:
                print(f"\n      🔍 DIAGNÓSTICO 403:")
                print(f"         - La API Key no tiene permisos para acceder a este recurso")
                print(f"         - Verifica los permisos de la API Key en Retell")
            elif e.status_code == 404:
                print(f"\n      🔍 DIAGNÓSTICO 404:")
                print(f"         - El endpoint no existe con este path template")
                print(f"         - El Call ID podría no existir en tu cuenta")
                print(f"         - El path template podría ser incorrecto")
            elif e.status_code == 429:
                print(f"\n      🔍 DIAGNÓSTICO 429:")
                print(f"         - Rate limit excedido")
                print(f"         - Espera unos minutos antes de intentar de nuevo")
            elif not e.status_code:
                print(f"\n      🔍 DIAGNÓSTICO:")
                print(f"         - Error de conexión o timeout")
                print(f"         - Verifica tu conexión a internet")
                print(f"         - Verifica que la URL base sea correcta")
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            print(f"\n   ❌ ERROR {error_type}:")
            print(f"      Mensaje: {error_msg[:200]}")
            
            if "401" in error_msg or "Unauthorized" in error_msg:
                print(f"\n      🔍 DIAGNÓSTICO: No autorizado - API Key incorrecta o inválida")
            elif "403" in error_msg or "Forbidden" in error_msg:
                print(f"\n      🔍 DIAGNÓSTICO: Prohibido - API Key sin permisos")
            elif "404" in error_msg:
                print(f"\n      🔍 DIAGNÓSTICO: No encontrado - Path template o Call ID incorrecto")
            elif "timeout" in error_msg.lower():
                print(f"\n      🔍 DIAGNÓSTICO: Timeout - Problema de conexión")
            elif "SSL" in error_msg or "certificate" in error_msg.lower():
                print(f"\n      🔍 DIAGNÓSTICO: Error SSL - Problema con certificados")
            elif "connection" in error_msg.lower():
                print(f"\n      🔍 DIAGNÓSTICO: Error de conexión - Verifica la URL base")
    
    print(f"\n{'='*80}")
    print("\n❌ Todas las pruebas fallaron")
    print("\n💡 Posibles soluciones:")
    print("   1. Verifica que la API Key sea correcta y completa en .env")
    print("   2. Verifica que el Call ID exista en tu cuenta de Retell")
    print("   3. Verifica la URL base en .env: RETELL_BASE_URL=...")
    print("   4. Verifica el path template en .env: RETELL_CALL_PATH_TEMPLATE=...")
    print("   5. Verifica que tengas conexión a internet")
    print("   6. Contacta con Retell para verificar la configuración de tu API")
    
    return False

if __name__ == "__main__":
    print("=" * 80)
    print("DIAGNÓSTICO DE CONEXIÓN CON API DE RETELL")
    print("=" * 80)
    test_retell_connection()