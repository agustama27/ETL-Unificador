# Resumen de Campos del Template Excel

## Estructura del Template

El template tiene **4 hojas**:
1. **CARGA INICIAL** - Donde se ingresan los datos (hoja principal de entrada)
2. **Cobranzas** - Muestra el cupón formateado (se completa automáticamente con fórmulas)
3. **LETRAS** - Tabla de conversión de números a letras
4. **Hoja1** - Tabla de sucursales

## Campos Identificados en "CARGA INICIAL"

### Información General
- **CID** (Celda D4) - Label: "CID:" (B4) - **VACÍO**
- **SUCURSAL** (Celda G4) - Label: "Sucursal:" (G4) - Tiene texto "Sucursal:"
- **FECHA_PAGO** (Celda N9) - Label: "FECHA DE PAGO" (N8) - Tiene fórmula =TODAY()

### Datos de Operación
- **CUENTA_CLIENTE** (Celda T9) - Label: "CUENTA CLIENTE" (T8) - **VACÍO**
- **MODULO** (Celda B12) - Label: "MÓDULO" (B11) - Valor: "201- GESTION Y MORA"
- **MONEDA** (Celda N12) - Label: "MONEDA" (N11) - Valor: "80 - Pesos"
- **NRO_OPERACION** (Celda B15) - Label: "N° DE OPERACIÓN" (B14) - **VACÍO**
- **TIPO_OPERACION** (Celda J15) - Label: "TIPO OPERACIÓN" (J14) - Valor: "Ingresar TIPOOPER"
- **PAPEL** (Celda Q15) - Label: "PAPEL" (Q14) - Valor: "Ingresar PAPEL"

### Datos del Cliente
- **TIPO_DOC** (Celda B18) - Label: "TIPO DOC." (B17) - Valor: "CUIT"
- **CUIL_CUIT** (Celda G18) - Label: "N° CUIT/CUIL" (G17) - **VACÍO**
- **NOMBRE_CLIENTE** (Celda L18) - Label: "APELLIDO Y NOMBRES / RAZON SOCIAL" (L17) - **VACÍO**

### Campos de Montos (en columnas AE+)
- **AE8** - Valor: 0
- **AE9** - Valor: 0
- **AE11** - Fórmula compleja
- **AE12** - Fórmula compleja
- **AE13** - Fórmula compleja

## Campos que Necesitan Completarse (Vacíos o con Placeholders)

1. **CID** (D4) - Vacío
2. **CUENTA_CLIENTE** (T9) - Vacío
3. **NRO_OPERACION** (B15) - Vacío
4. **TIPO_OPERACION** (J15) - Tiene placeholder "Ingresar TIPOOPER"
5. **PAPEL** (Q15) - Tiene placeholder "Ingresar PAPEL"
6. **CUIL_CUIT** (G18) - Vacío
7. **NOMBRE_CLIENTE** (L18) - Vacío
8. **SUCURSAL** (G4) - Tiene texto "Sucursal:" (probablemente necesita el número de sucursal)

## Nota Importante

Los datos se ingresan en la hoja **"CARGA INICIAL"** y se reflejan automáticamente en la hoja **"Cobranzas"** mediante fórmulas. Por lo tanto, para completar el cupón debemos escribir los valores en "CARGA INICIAL".

