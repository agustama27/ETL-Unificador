# soho-clarouy-encuestas-etl

Sistema ETL Python para procesamiento de encuestas post-contacto de **Claro Uruguay**.

## Propósito

Este proyecto automatiza el procesamiento de encuestas ejecutadas por un agente de voz de Retell.ai. El sistema:

1. **back-base**: Procesa la base de clientes y genera archivos de teléfonos para cargar en Retell
2. **back-resultados**: Consulta la API de Retell, integra datos de gestión humana (ROMAN) y genera un CSV de análisis interno con 26 columnas

## Estructura

```
soho-clarouy-encuestas-etl/
├── back-base/           # Módulo 1: Procesamiento de base de clientes
├── back-resultados/     # Módulo 2: Resultados de encuestas (Retell + ROMAN)
├── skills/              # Skills de IA reutilizables
└── AGENTS.md           # Documentación raíz
```

## Requisitos

- Python 3.12+
- pandas
- requests
- python-dotenv
- tqdm

## Instalación

```bash
# Instalar dependencias
pip install -r back-base/requirements.txt
pip install -r back-resultados/requirements.txt
```

## Configuración

### back-resultados

Crear archivo `.env` en `back-resultados/`:

```
RETELL_API_KEY=tu_api_key_aqui
USE_ROMAN=true
```

## Uso

### Módulo 1: Procesar base de clientes

```bash
python back-base/main.py
```

Input: CSV en `back-base/base-recibida/`

Output:
- `back-base/base-generada/con-filtros/base_clarouy_DDMMAAAA.csv`
- `back-base/base-generada/con-filtros/telefonos_x_cliente_DDMMAAAA.csv`

### Módulo 2: Procesar resultados de encuestas

```bash
python back-resultados/main.py
```

Input:
- `back-resultados/calls/` — CSV con call_ids
- `back-resultados/roman/` — CSV con datos ROMAN (opcional)

Output:
- `back-resultados/results/encuestas_clarouy_DDMMAAAA.csv`

## Documentación

- [AGENTS.md](./AGENTS.md) — Documentación raíz para agentes de IA
- [back-base/AGENTS.md](./back-base/AGENTS.md)
- [back-resultados/AGENTS.md](./back-resultados/AGENTS.md)

## Patrones Implementados

- **Multi-encoding CSV**: Detección automática de codificación (`utf-8`, `latin-1`, `iso-8859-1`, `cp1252`, `utf-16`)
- **Llamadas paralelas**: `ThreadPoolExecutor` con 100 workers
- **Búsqueda recursiva JSON**: Navegación de campos anidados
- **Merge inteligente**: ROMAN sobrescribe datos de Retell para campos de tipificación
- **CSV europeo**: Separador `;`, decimal `,`
