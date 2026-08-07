# ETL Pipeline - Survey Data Processing

ETL system for transforming Excel survey data into CSV format compatible with n8n workflow for Retell AI agent processing.

## Overview

This ETL pipeline processes survey data from Excel files, applies business transformations, and outputs CSV files that can be consumed by an n8n workflow for AI-powered customer surveys.

### Key Features

- Extracts data from Excel files (15 input columns)
- Creates `customer_name` by concatenating first and last names
- Normalizes phone numbers to match n8n workflow logic
- Maps and transforms data to 14 output columns
- Validates data quality
- Outputs CSV in n8n-compatible format

## Project Structure

```
soho-encuestaCX/
├── back-base/                 # ETL processing code
│   ├── config.py             # Configuration management
│   ├── main.py               # ETL orchestration entry point
│   ├── etl/
│   │   ├── extractor.py      # Excel reading logic
│   │   ├── transformer.py    # Data transformation
│   │   ├── validators.py     # Data validation
│   │   └── loader.py         # CSV writing logic
│   ├── utils/
│   │   ├── logger.py         # Logging configuration
│   │   └── phone_normalizer.py  # Phone normalization (matches n8n)
│   └── tests/
│       ├── test_phone_normalizer.py
│       └── test_transformer.py
├── back-resultados/          # Future results processing
├── input/                    # Input Excel files
│   └── Entrevista CX 2° semestre 2025.xlsx
├── output/                   # Generated CSV files
│   └── base_encuesta.csv
├── logs/                     # Execution logs
├── workflow ejemplo/         # n8n workflow reference
│   └── ENCUESTA-inbound-wh.json
├── requirements.txt          # Python dependencies
├── .venv                     # Virtual environment marker
├── .gitignore               # Git ignore patterns
└── README.md                # This file
```

## Installation

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

### Setup

1. Create and activate virtual environment:

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Unix/MacOS
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Run the ETL pipeline with default settings:

```bash
python back-base/main.py
```

### What Happens

The pipeline executes 5 steps:

1. **Extract**: Reads Excel file from `input/Entrevista CX 2° semestre 2025.xlsx`
2. **Transform**: Applies business transformations
   - Creates `customer_name` from Nombre + Apellido
   - Normalizes `phone_number` from Teléfono
   - Maps 15 input columns to 14 output columns
3. **Validate**: Checks data quality
   - Validates required fields
   - Checks email format
   - Validates phone numbers
4. **Load**: Writes CSV to `output/base_encuesta.csv`
5. **Verify**: Validates output CSV format

### Output

- **CSV File**: `output/base_encuesta.csv`
- **Backup**: `output/base_encuesta_YYYYMMDD_HHMMSS.csv`
- **Logs**: `logs/etl_YYYYMMDD_HHMMSS.log`

## Data Transformation

### Input Format (Excel)

15 columns:
1. Tier
2. Cliente
3. Gerencia Cliente
4. Vertical de negocio
5. Nombre
6. Apellido
7. Puesto
8. Referente
9. Jerarquia
10. Mail
11. Teléfono
12. Provincia
13. País
14. Evoltis: Referente operativo
15. Evoltis: Referente de negocio

### Output Format (CSV)

14 columns (lowercase, snake_case):
1. `tier`
2. `cliente`
3. `gerencia_cliente`
4. `vertical_de_negocio`
5. `customer_name` (NEW - concatenated)
6. `puesto`
7. `referente`
8. `jerarquia`
9. `mail`
10. `phone_number` (NORMALIZED)
11. `provincia`
12. `pais`
13. `referente_operativo`
14. `referente_negocio`

### Key Transformations

#### 1. Customer Name Creation

Concatenates `Nombre` + `Apellido` with space:
- Input: Nombre="Carolina", Apellido="Aguirre"
- Output: customer_name="Carolina Aguirre"

Handles missing values gracefully:
- If both exist: "Nombre Apellido"
- If only one: uses available value
- If neither: empty string

#### 2. Phone Normalization

Matches n8n workflow JavaScript logic exactly:
- Removes `+` prefix
- Removes all non-digit characters (spaces, dashes, parentheses)
- Handles decimal format (e.g., "3454400185.0" → "3454400185")
- Returns empty string for null/None values

Examples:
```
"+54 9 11 1234-5678" → "5491112345678"
"3454400185.0"       → "3454400185"
"+351 284 3724"      → "3512843724"
None                 → ""
```

## Testing

### Run All Tests

```bash
cd back-base
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_phone_normalizer.py -v
pytest tests/test_transformer.py -v
```

### Run with Coverage

```bash
pytest tests/ -v --cov=. --cov-report=html
```

View coverage report: `htmlcov/index.html`

## Configuration

Edit [back-base/config.py](back-base/config.py) to customize:

- Input/output file paths
- CSV delimiter and encoding
- Column mappings
- Required fields
- Logging level

## Logging

Logs are written to:
- **Console**: INFO level and above (colored output if colorlog installed)
- **File**: DEBUG level and above in `logs/etl_YYYYMMDD_HHMMSS.log`

Log format:
```
[2026-01-27 16:30:45] [INFO] [etl.extractor] Extracted 140 rows
[2026-01-27 16:30:45] [WARNING] [etl.validator] Field 'mail' is empty in 2 rows
[2026-01-27 16:30:46] [INFO] [etl.loader] Saved to output/base_encuesta.csv
```

## Validation Rules

### Required Fields

These fields must not be empty:
- `tier`
- `cliente`
- `customer_name`
- `mail`
- `phone_number`

### Email Validation

- Must match format: `user@domain.com`
- Uses email-validator library

### Phone Validation

After normalization:
- Must contain only digits
- Length between 8-15 digits

## Troubleshooting

### Common Issues

#### 1. Excel File Not Found

```
ERROR: Input file not found: input/Entrevista CX 2° semestre 2025.xlsx
```

**Solution**: Ensure Excel file is in the `input/` directory

#### 2. Missing Columns

```
ERROR: Missing required columns: {'Nombre', 'Apellido'}
```

**Solution**: Verify Excel file has all 15 expected columns

#### 3. Permission Denied

```
ERROR: Permission denied writing to output/base_encuesta.csv
```

**Solution**:
- Close the CSV file if open in Excel
- Check file permissions
- Ensure output directory is writable

#### 4. Import Errors

```
ModuleNotFoundError: No module named 'pandas'
```

**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

## n8n Workflow Integration

The output CSV (`base_encuesta.csv`) is designed for the n8n workflow:

1. Upload CSV to OneDrive (or configured location)
2. n8n workflow downloads CSV when triggered
3. Workflow receives inbound call with phone number
4. Workflow normalizes incoming phone number (same logic as ETL)
5. Workflow searches CSV for matching phone number
6. Workflow extracts all 14 variables from matched row
7. Variables passed to Retell AI agent via webhook

**Critical**: Phone normalization in ETL must match n8n workflow exactly for successful lookups.

## Development

### Adding New Transformations

1. Edit [back-base/etl/transformer.py](back-base/etl/transformer.py)
2. Add transformation method
3. Call method in `transform()` pipeline
4. Add tests in [back-base/tests/test_transformer.py](back-base/tests/test_transformer.py)

### Adding New Validations

1. Edit [back-base/etl/validators.py](back-base/etl/validators.py)
2. Add validation method
3. Call method in `validate()` pipeline
4. Add tests

### Modifying Column Mappings

Edit [back-base/config.py](back-base/config.py):
- `INPUT_COLUMNS`: Expected Excel column names
- `OUTPUT_COLUMNS`: Desired CSV column names
- `COLUMN_MAPPING`: Direct column mappings

## Performance

- Processes 140 rows in ~3 seconds
- Memory efficient for files up to 10K rows
- For larger files, consider chunked processing

## License

Internal use - Soho/Evoltis projects

## Support

For issues or questions:
- Check logs in `logs/` directory
- Review error messages in console output
- Verify input Excel file format matches expected structure

## Version History

- **v1.0.0** (2026-01-27): Initial implementation
  - Excel to CSV ETL pipeline
  - Phone normalization matching n8n workflow
  - Customer name concatenation
  - Data validation
  - Comprehensive logging
  - Unit tests
