# Back Carga Masiva - CRM Bancor

Módulo ETL para generar archivos Excel (.xlsx) compatibles con el sistema de cargas masivas del CRM de Banco de Córdoba (Bancor).

## Descripción

Este módulo procesa los datos de gestiones de cobranza obtenidos de Retell.ai y ROMAN, transformándolos al formato específico requerido por el CRM de Bancor para cargas masivas.

## Estructura de Carpetas

```
back-cargaMasiva/
├── calls/              # CSV con Call IDs de Retell (input)
├── roman/              # CSV con datos de ROMAN (input)
├── output/             # Archivos XLSX generados (output)
├── plantilla/          # Plantilla de ejemplo del formato
├── procesos/
│   ├── config_catalogos.py   # Catálogos de estados, sub-estados, responsables
│   ├── validador.py          # Validaciones de datos
│   ├── mapeador.py           # Mapeo de campos Retell/ROMAN → CRM
│   └── excel_generator.py    # Generación de archivo XLSX
├── main.py             # Script principal
└── README.md
```

## Uso

### Requisitos Previos

1. Tener configurada la variable de entorno `RETELL_API_KEY`
2. Colocar los archivos CSV de entrada en las carpetas correspondientes

### Ejecución

```bash
cd back-cargaMasiva
python main.py
```

### Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `RETELL_API_KEY` | Clave API de Retell.ai | (requerida) |
| `USE_ROMAN` | Habilitar integración con ROMAN | `true` |
| `ESTUDIO` | Nombre del estudio/gestor | `EVOLTIS` |

### Ejemplo

```bash
# Usar con ROMAN habilitado (default)
python main.py

# Usar sin ROMAN
set USE_ROMAN=false
python main.py

# Especificar estudio
set ESTUDIO=KONECTA
python main.py
```

## Formato de Salida

El archivo generado es un Excel (.xlsx) con una hoja llamada "MODELO envio" que contiene 13 columnas:

| # | Columna | Tipo | Obligatorio |
|---|---------|------|-------------|
| 1 | Clase de Operación | Texto | Sí (siempre "ZCE1") |
| 2 | Estado | Texto | Sí |
| 3 | Sub- Estado | Texto | Condicional |
| 4 | CUIT | Número | Sí (11 dígitos) |
| 5 | Cuenta | Número | No |
| 6 | Desc. Acuerdo Comercial | Texto | No |
| 7 | Acuerdo Comercial | Número | No |
| 8 | Responsable | Número | Sí |
| 9 | Descripción | Texto | Sí (máx 100 chars) |
| 10 | Persona de Contacto | Texto | No |
| 11 | Juzgado | Texto | No |
| 12 | Garante | Texto | No |
| 13 | Notas | Texto | No |

## Estados Válidos

### Estados sin Sub-Estado

- E0004: Contactado con terceros
- E0005: Sin Contacto con Titular
- E0006: Aduce Fallecimiento
- E0014: Asignación prejudicial
- E0020: PdP Total Incumplida
- E0021: Carta
- E0022: PdP Parcial Cumplida
- E0023: Sin voluntad de pago
- E0024: IVR
- E0025: Contactado con Titular
- E0026: PdP Parc. Ac. Cumplida
- E0027: PdP Parcial Incumplida
- E0028: PdP Parc. Ac. Incumplida
- E0029: Refinanciación
- E0030: Sin datos de Contactación

### Estados con Sub-Estado Obligatorio

**E0012 - Promesa de Pago Pactada:**
- E001: Parcial
- E002: Parcial Acordado
- E003: Total

**E0002 - Gestión de Refinanciación:**
- E001: En curso / Recibida
- E002: Enviada a Bancor / Con Observaciones
- E003: Enviada a liquidar

## Responsables

| Código | Estudio |
|--------|---------|
| 7000004923 | ALTERMAN |
| 7000002877 | DIAZ YOFRE |
| 5000000786 | EVOLTIS |
| 5000000784 | GEEX |
| 7000002901 | JLC |
| 5000000785 | KONECTA |
| 7000005550 | RECOVERY MANAGEMENT |
| 7000002878 | TILLARD |
| 7000005647 | TONELLI |
| 7000002897 | VILATTA |

## Instrucciones de Envío

- **Días de carga**: Miércoles y Viernes
- **Horario límite**: 12:30 hrs
- **Email destino**: Mora_Prejudicial_Estudios@bancor.com.ar
- **Asunto**: "Cargas masivas CRM (FECHA) (NOMBRE ESTUDIO)"
