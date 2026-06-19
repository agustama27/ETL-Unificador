# Sistema de Generación de Base Bancor

Sistema integral para el procesamiento y gestión de datos bancarios de Bancor, incluyendo procesamiento de bases de clientes, generación de cupones y análisis de resultados de llamadas.

## Descripción General

Este proyecto está diseñado para automatizar el procesamiento de datos bancarios, facilitando la gestión de información de clientes, generación de documentos y análisis de resultados de llamadas. El sistema está organizado en módulos independientes, cada uno con su propia funcionalidad específica.

## Estructura del Proyecto

El proyecto está organizado en tres módulos principales:

```
bancor-generadorBase/
├── back-base/          # Procesamiento de base de clientes
├── back-cupones/       # Generación de cupones
└── back-resultados/    # Procesamiento de resultados de llamadas Retell.ai
```

## Módulos

### 📊 back-base
**Procesamiento de Base de Clientes Bancor**

Módulo encargado de procesar archivos CSV de base de clientes bancarios, aplicando validaciones, filtros y transformaciones para generar archivos consolidados.

**Funcionalidades principales:**
- Procesamiento y consolidación de datos de clientes
- Filtrado por criterios específicos (OFERTA_Importe, ModuloCodigo)
- Generación de base consolidada por cliente
- Extracción y consolidación de teléfonos por cliente

**Archivos generados:**
- `base_bancor_DDMMAAAA.csv` - Base consolidada de clientes
- `telefonos_x_cliente_DDMMAAAA.csv` - Teléfonos consolidados por cliente

📖 **Ver documentación completa:** [back-base/README.md](back-base/README.md)

---

### 📞 back-resultados
**Procesamiento de Resultados de Llamadas Retell.ai**

Módulo que procesa los resultados de las llamadas obtenidas desde Retell.ai, extrayendo variables dinámicas y datos postcall para generar un CSV consolidado con todas las gestiones.

**Funcionalidades principales:**
- Lectura de Call IDs desde archivos CSV
- Consulta a la API de Retell.ai para obtener datos de llamadas
- Extracción de variables dinámicas y datos postcall
- Generación de CSV con todas las gestiones

**Archivos generados:**
- `gestiones_bancor_DDMMAAAA.csv` - CSV con todas las gestiones de llamadas

📖 **Ver documentación completa:** [back-resultados/README.md](back-resultados/README.md)

---

### 🎫 back-cupones
**Generación de Cupones**

Módulo para la generación de cupones bancarios a partir de templates y datos procesados.

**Funcionalidades principales:**
- Generación de cupones desde templates Excel
- Procesamiento de datos para cupones

📖 **Documentación:** En desarrollo

---

## Requisitos Generales

### Dependencias Python

```bash
pip install pandas requests python-dotenv openpyxl
```

### Variables de Entorno

Algunos módulos requieren configuración de variables de entorno. Consulta la documentación específica de cada módulo para más detalles.

## Inicio Rápido

### Procesamiento de Base de Clientes

```bash
cd back-base
python main.py
```

### Procesamiento de Resultados de Llamadas

```bash
cd back-resultados
python main.py
```

## Documentación

Cada módulo tiene su propio README con documentación detallada:

- **[back-base/README.md](back-base/README.md)** - Documentación completa del procesamiento de base de clientes
- **[back-resultados/README.md](back-resultados/README.md)** - Documentación completa del procesamiento de resultados de llamadas

Cada README incluye:
- Descripción detallada del módulo
- Estructura de carpetas
- Requisitos y configuración
- Guía paso a paso de ejecución
- Validaciones realizadas
- Estructura de archivos generados
- Manejo de errores
- Ejemplos de uso

## Notas Importantes

1. **Independencia de módulos**: Cada módulo funciona de forma independiente y puede ejecutarse por separado
2. **Archivos de entrada**: Cada módulo requiere archivos de entrada en carpetas específicas. Consulta la documentación de cada módulo para más detalles
3. **Formato de fechas**: Los archivos generados utilizan formato DDMMAAAA en sus nombres
4. **Codificación**: Los archivos CSV utilizan principalmente codificación UTF-8, con soporte para otras codificaciones cuando sea necesario

## Soporte

Para problemas o consultas específicas de cada módulo, consulta la documentación detallada en el README correspondiente:

- Problemas con procesamiento de base: [back-base/README.md](back-base/README.md)
- Problemas con resultados de llamadas: [back-resultados/README.md](back-resultados/README.md)

## Licencia

Este proyecto es de uso interno para Bancor.

