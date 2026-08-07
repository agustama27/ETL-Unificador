"""
Cliente para la API de Retell AI
Maneja consultas a la API con retry logic y rate limiting
"""

import requests
import logging
import time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


logger = logging.getLogger(__name__)


class RetellAPIClient:
    """Cliente para interactuar con la API de Retell AI"""

    def __init__(self, api_key: str, base_url: str):
        """
        Inicializar cliente de API

        Args:
            api_key: API key de Retell
            base_url: URL base de la API (ej: https://api.retellai.com/v2)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')

        # Configurar sesión con headers
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

        logger.info("Cliente API de Retell inicializado")

    def get_call_details(self, call_id: str, max_retries: int = 3) -> Optional[Dict]:
        """
        Obtener detalles de una llamada con retry logic

        Args:
            call_id: ID de la llamada
            max_retries: Número máximo de reintentos (default: 3)

        Returns:
            Optional[Dict]: Detalles de la llamada o None si falla

        Raises:
            requests.exceptions.RequestException: En caso de error no recuperable
        """
        url = f"{self.base_url}/get-call/{call_id}"
        attempt = 0

        while attempt < max_retries:
            try:
                response = self.session.get(url, timeout=30)

                # Manejar diferentes códigos de estado
                if response.status_code == 200:
                    logger.debug(f"Call {call_id}: Fetch exitoso")
                    return response.json()

                elif response.status_code == 404:
                    logger.warning(f"Call {call_id}: 404 Not Found")
                    return None

                elif response.status_code == 429:
                    # Rate limit - esperar y reintentar
                    retry_after = int(response.headers.get('Retry-After', 5))
                    logger.warning(
                        f"Call {call_id}: Rate limit (429). "
                        f"Esperando {retry_after}s..."
                    )
                    time.sleep(retry_after)
                    attempt += 1
                    continue

                elif response.status_code == 401:
                    # API key inválida - no reintentar
                    logger.error("Error 401: API key inválida")
                    raise requests.exceptions.RequestException(
                        "API key inválida. Verifique RETELL_API_KEY en .env"
                    )

                elif response.status_code >= 500:
                    # Error del servidor - reintentar con backoff
                    wait_time = 2 ** attempt  # Backoff exponencial: 1s, 2s, 4s
                    logger.warning(
                        f"Call {call_id}: Error {response.status_code}. "
                        f"Reintentando en {wait_time}s... (intento {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    attempt += 1
                    continue

                else:
                    logger.error(
                        f"Call {call_id}: Error {response.status_code} - {response.text}"
                    )
                    return None

            except requests.exceptions.Timeout:
                wait_time = 2 ** attempt
                logger.warning(
                    f"Call {call_id}: Timeout. "
                    f"Reintentando en {wait_time}s... (intento {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)
                attempt += 1
                continue

            except requests.exceptions.RequestException as e:
                logger.error(f"Call {call_id}: Error de red - {e}")
                return None

        # Si llegamos aquí, se agotaron los reintentos
        logger.error(f"Call {call_id}: Falló después de {max_retries} intentos")
        return None

    def extract_dynamic_variables(self, call_details: Dict) -> Dict:
        """
        Extraer variables dinámicas del response de la API

        Args:
            call_details: Respuesta JSON de get-call

        Returns:
            Dict: Variables dinámicas extraídas
        """
        if not call_details:
            return {
                'dni_cliente': None,
                'credito': None,
                'monto_exacto': None,
                'customer_name': None,
                'user_number': None
            }

        # Intentar extraer desde retell_llm_dynamic_variables
        dynamic_vars = call_details.get('retell_llm_dynamic_variables', {})

        return {
            'dni_cliente': dynamic_vars.get('dni_cliente'),
            'credito': dynamic_vars.get('credito'),
            'monto_exacto': dynamic_vars.get('monto_exacto'),
            'customer_name': dynamic_vars.get('customer_name'),
            'user_number': dynamic_vars.get('user_number')
        }

    def extract_analysis_variables(self, call_details: Dict) -> Dict:
        """
        Extraer variables de análisis del response de la API

        Args:
            call_details: Respuesta JSON de get-call

        Returns:
            Dict: Variables de análisis extraídas
        """
        if not call_details:
            return self._get_empty_analysis_dict()

        # Intentar extraer desde call_analysis.custom_analysis_data
        call_analysis = call_details.get('call_analysis', {})
        custom_data = call_analysis.get('custom_analysis_data', {})

        return {
            'campaign_id': custom_data.get('campaign_id'),
            'contact_id': custom_data.get('contact_id'),
            'contacto_efectivo': custom_data.get('contacto_efectivo'),
            'tipo_contacto': custom_data.get('tipo_contacto'),
            'speech_completo': custom_data.get('speech_completo'),
            'motivo_no_entrega': custom_data.get('motivo_no_entrega'),
            'resultado_solicitud': custom_data.get('resultado_solicitud'),
            'resultado_efectivamente_informado': custom_data.get('resultado_efectivamente_informado'),
            'hubo_interaccion': custom_data.get('hubo_interaccion'),
            'tipo_interaccion': custom_data.get('tipo_interaccion'),
            'menciona_0800': custom_data.get('menciona_0800'),
            'objetivo_cumplido': custom_data.get('objetivo_cumplido'),
            'sentimiento_cliente': custom_data.get('sentimiento_cliente'),
            'interrupcion_al_bot': custom_data.get('interrupcion_al_bot'),
            'duracion_total_seg': custom_data.get('duracion_total_seg'),
            'tiempo_habla_cliente_seg': custom_data.get('tiempo_habla_cliente_seg'),
            'tiempo_habla_bot_seg': custom_data.get('tiempo_habla_bot_seg'),
            'motivo_reintento': custom_data.get('motivo_reintento')
        }

    def extract_metadata(self, call_details: Dict) -> Dict:
        """
        Extraer metadata del response de la API

        Args:
            call_details: Respuesta JSON de get-call

        Returns:
            Dict: Metadata extraída
        """
        if not call_details:
            return {
                'script_version': None,
                'call_datetime': None
            }

        # Intentar extraer metadata
        metadata = call_details.get('metadata', {})

        # Extraer script_version desde metadata
        script_version = metadata.get('script_version')

        # Extraer call_datetime desde start_timestamp (convertir a ISO)
        call_datetime = None
        start_timestamp = call_details.get('start_timestamp')
        if start_timestamp:
            try:
                from datetime import datetime
                call_datetime = datetime.fromtimestamp(start_timestamp / 1000).isoformat()
            except Exception as e:
                logger.warning(f"No se pudo convertir timestamp: {e}")

        return {
            'script_version': script_version,
            'call_datetime': call_datetime
        }

    def batch_fetch_calls(self, call_ids: List[str], max_workers: int = 5) -> Dict[str, Optional[Dict]]:
        """
        Obtener múltiples llamadas en paralelo

        Args:
            call_ids: Lista de Call IDs a obtener
            max_workers: Número máximo de workers paralelos (default: 5)

        Returns:
            Dict[str, Optional[Dict]]: Mapeo de call_id -> call_details
        """
        logger.info(f"Obteniendo detalles para {len(call_ids)} llamadas...")

        results = {}
        successful = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Enviar todas las tareas
            future_to_call_id = {
                executor.submit(self.get_call_details, call_id): call_id
                for call_id in call_ids
            }

            # Procesar resultados a medida que completan
            for i, future in enumerate(as_completed(future_to_call_id), 1):
                call_id = future_to_call_id[future]

                try:
                    call_details = future.result()
                    results[call_id] = call_details

                    if call_details:
                        successful += 1
                    else:
                        failed += 1

                except Exception as e:
                    logger.error(f"Call {call_id}: Excepción - {e}")
                    results[call_id] = None
                    failed += 1

                # Log de progreso cada 10 llamadas
                if i % 10 == 0 or i == len(call_ids):
                    logger.info(f"Progreso: {i}/{len(call_ids)} llamadas procesadas")

        logger.info(
            f"Fetch API completo: {successful}/{len(call_ids)} exitosas, {failed} fallidas"
        )

        return results

    def _get_empty_analysis_dict(self) -> Dict:
        """Retornar diccionario vacío para variables de análisis"""
        return {
            'campaign_id': None,
            'contact_id': None,
            'contacto_efectivo': None,
            'tipo_contacto': None,
            'speech_completo': None,
            'motivo_no_entrega': None,
            'resultado_solicitud': None,
            'resultado_efectivamente_informado': None,
            'hubo_interaccion': None,
            'tipo_interaccion': None,
            'menciona_0800': None,
            'objetivo_cumplido': None,
            'sentimiento_cliente': None,
            'interrupcion_al_bot': None,
            'duracion_total_seg': None,
            'tiempo_habla_cliente_seg': None,
            'tiempo_habla_bot_seg': None,
            'motivo_reintento': None
        }
