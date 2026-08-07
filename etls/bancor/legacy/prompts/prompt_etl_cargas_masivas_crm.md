Contexto del Proyecto:
Necesito crear un sistema ETL (Extract, Transform, Load) en Python para procesar gestiones de cobranza y generar archivos Excel compatibles con el sistema de cargas masivas del CRM de Banco de Córdoba (Bancor).

Objetivo:
Quiero generar una nueva carpeta back-cargaMasiva en el que se procesen nuevamente los datos de salida/resultados, pero esta vez con distinto formato y especificaciones.
Desde la rama feature/deduplicacion-telefonos crea otra para comenzar con este nuevo desarrollo.

Intput:
Quiero mantener la misma estructura y manejo de los intputs que en la carpeta back-resultados/
Se va a recibir un archivo de ROMAN en roman/ y un archivo de Retell en results/
Intenta replicar en la nueva carpeta back-cargaMasiva/ los procesos necesarios pero que se acoplen a las nuevas especificaciones de Output.

Output:
La estructura del archivo del output debe de ser un archivo en formato xlsx como @back-cargaMasiva/plantilla/Carga Masiva Gestiones CRM Bancor - ejemplo(MODELO envio).csv  . Recuerda que debe de ser en formato xlsx

---

## Estructura del Archivo de Salida

El archivo de salida debe ser un Excel (.xlsx) con una única hoja llamada **"MODELO envio"** que contenga las siguientes columnas en este orden exacto:

| # | Columna | Tipo | Obligatorio | Descripción |
|---|---------|------|-------------|-------------|
| 1 | Clase de Operación | Texto | Sí | Siempre debe ser `ZCE1` |
| 2 | Estado | Texto | Sí | Código de estado (ver tabla de estados) |
| 3 | Sub- Estado | Texto | Condicional | Código de sub-estado (solo para ciertos estados) |
| 4 | CUIT | Número | Sí | CUIT del cliente (11 dígitos, sin guiones) |
| 5 | Cuenta | Número | No | Número de cuenta (opcional) |
| 6 | Desc. Acuerdo Comercial | Texto | No | Descripción del acuerdo (opcional) |
| 7 | Acuerdo Comercial | Número | No | Código de acuerdo (opcional) |
| 8 | Responsable | Número | Sí | Número de responsable (ver tabla de responsables) |
| 9 | Descripción | Texto | Sí | **Máximo 100 caracteres**. Descripción de la gestión |
| 10 | Persona de Contacto | Texto | No | Nombre del contacto (opcional) |
| 11 | Juzgado | Texto | No | Juzgado asignado (opcional) |
| 12 | Garante | Texto | No | Información del garante (opcional) |
| 13 | Notas | Texto | No | Notas adicionales (opcional) |

---

## Catálogo de Estados (DETALLE TIPI)

### Estados sin Sub-Estado

| Código | Descripción |
|--------|-------------|
| E0004 | 03. Contactado con terceros |
| E0021 | 04. Carta |
| E0024 | 05. IVR |
| E0025 | 06. Contactado con Titular |
| E0020 | 07ti. PdP Total Incumplida |
| E0022 | 07pc. PdP Parcial Cumplida |
| E0026 | 7pac. PdP Parc. Ac. Cumplida |
| E0027 | 7pi. PdP Parcial Incumplida |
| E0028 | 7pai. PdP Parc. Ac. Incumplida |
| E0029 | 09. Refinanciación |
| E0005 | 10. Sin Contacto con Titular |
| E0030 | 11. Sin datos de Contactación |
| E0023 | 12. Sin voluntad de pago |
| E0006 | 13. Aduce Fallecimiento |
| E0003 | 14. Posible Fraude |
| E0014 | Asignación prejudicial (inicial) |

### Estados CON Sub-Estado Obligatorio

#### Estado E0012 - 07. Promesa de Pago Pactada
| Sub-Estado | Descripción | Nota |
|------------|-------------|------|
| E001 | Parcial | Ingresar N° operación e importe |
| E002 | Parcial Acordado | Ingresar N° operación e importe |
| E003 | Total | Ingresar N° operación e importe |

#### Estado E0002 - 08. Gestión de Refinanciación
| Sub-Estado | Descripción | Nota |
|------------|-------------|------|
| E001 | En curso / Recibida | Ingresar plazo e importe cuenta |
| E002 | Enviada a Bancor / Con Observaciones | - |
| E003 | Enviada a liquidar | - |

---

## Tabla de Responsables

| N° Responsable | Estudio/Gestor |
|----------------|----------------|
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

---

## Reglas de Validación

1. **CUIT**: Debe ser numérico de 11 dígitos
2. **Descripción**: NO debe superar los 100 caracteres (truncar si es necesario)
3. **Estado**: Debe ser un código válido de la tabla de estados
4. **Sub-Estado**: 
   - Obligatorio si el Estado es E0012 o E0002
   - Debe dejarse vacío para otros estados
5. **Responsable**: Debe ser un número válido de la tabla de responsables
6. **Clase de Operación**: Siempre debe ser "ZCE1"

---

## Requerimientos del ETL

### Funcionalidades Principales

1. **Lectura de datos de entrada**: 
   - Soportar múltiples formatos (CSV, Excel, JSON)
   - Mapear columnas del archivo fuente a las columnas destino

2. **Transformación de datos**:
   - Validar y formatear CUIT (remover guiones, validar longitud)
   - Mapear estados/sub-estados según catálogo
   - Mapear nombre de estudio a número de responsable
   - Truncar descripción a 100 caracteres si excede
   - Limpiar caracteres especiales que puedan causar problemas

3. **Validaciones**:
   - Verificar que estados y sub-estados sean válidos
   - Verificar que el responsable exista en la tabla
   - Verificar que campos obligatorios estén completos
   - Generar reporte de errores/registros rechazados

4. **Generación de salida**:
   - Crear archivo Excel con formato exacto de "MODELO envio"
   - Nombrar archivo como: `YYYY-MM-DD_NOMBRE_ESTUDIO.xlsx`
   - Generar solo la hoja "MODELO envio" sin las hojas de referencia

### Estructura de Código Sugerida

```
proyecto_etl_crm/
├── config/
│   ├── estados.py          # Catálogo de estados y sub-estados
│   ├── responsables.py     # Tabla de responsables
│   └── settings.py         # Configuraciones generales
├── src/
│   ├── extract.py          # Funciones de lectura de datos
│   ├── transform.py        # Funciones de transformación y validación
│   ├── load.py             # Funciones de generación de Excel
│   └── validators.py       # Validadores de campos
├── utils/
│   └── helpers.py          # Funciones auxiliares
├── main.py                 # Script principal
├── requirements.txt        # Dependencias (pandas, openpyxl)
└── README.md               # Documentación
```

### Ejemplo de Uso Esperado

```python
from etl_crm import ETLCargaMasiva

# Inicializar ETL
etl = ETLCargaMasiva(
    archivo_entrada="gestiones_semana.csv",
    estudio="EVOLTIS"
)

# Ejecutar proceso
resultado = etl.procesar()

# Ver estadísticas
print(f"Registros procesados: {resultado.procesados}")
print(f"Registros válidos: {resultado.validos}")
print(f"Registros con error: {resultado.errores}")

# Archivo generado
print(f"Archivo de salida: {resultado.archivo_salida}")
```

---

## Especificaciones Adicionales del Cliente

- **Días de carga**: Miércoles y Viernes
- **Horario límite**: 12:30 hrs
- **Envío por email**: Mora_Prejudicial_Estudios@bancor.com.ar
- **Asunto del mail**: "Cargas masivas CRM (FECHA) (NOMBRE ESTUDIO/GESTOR)"
- **Formato de archivo**: Excel (.xlsx) con solo la hoja "MODELO envio"

---

## Consideraciones Técnicas

1. Usar `pandas` para manipulación de datos
2. Usar `openpyxl` para generar el archivo Excel final
3. Implementar logging para trazabilidad
4. Manejar excepciones de forma robusta
5. Generar archivo de errores/rechazados para revisión manual

---

## Ejemplo de Datos de Salida

| Clase de Operación | Estado | Sub- Estado | CUIT | Cuenta | Desc. Acuerdo Comercial | Acuerdo Comercial | Responsable | Descripción | Persona de Contacto | Juzgado | Garante | Notas |
|--------------------|--------|-------------|------|--------|------------------------|-------------------|-------------|-------------|---------------------|---------|---------|-------|
| ZCE1 | E0014 | | 11223334445 | | | | 5000000786 | Asignacion prejudicial | | | | |
| ZCE1 | E0025 | | 11223334445 | | | | 5000000786 | Notificacion via MAIL Y SMS | | | | |
| ZCE1 | E0012 | E001 | 11223334445 | | | | 5000000786 | abona cupon por 150000 el dia 25/11 | | | | |
| ZCE1 | E0012 | E003 | 11223334445 | | | | 5000000786 | abona cupon por 1500000 el dia 25/02 | | | | |
| ZCE1 | E0002 | E001 | 11223334445 | | | | 5000000786 | ref con entrega de 2000000 a 24 meses | | | | |

---

## Notas Importantes

⚠️ **El archivo de salida NO debe contener las hojas de referencia (DETALLE TIPI y TABLA RESPONSABLE)**. Solo debe incluir la hoja "MODELO envio" con los datos procesados.

⚠️ **El formato debe mantenerse exactamente igual** para evitar rechazos del sistema CRM.

⚠️ **La descripción tiene un límite estricto de 100 caracteres**.
