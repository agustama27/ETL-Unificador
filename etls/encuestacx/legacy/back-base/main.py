"""
Main ETL pipeline orchestration.

This script extracts data from Excel, transforms it according to business rules,
validates the output, and loads it to CSV for n8n workflow consumption.
"""
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from utils.logger import setup_logger
from etl.extractor import ExcelExtractor
from etl.transformer import DataTransformer
from etl.validators import DataValidator
from etl.loader import CSVLoader


def print_banner():
    """Print ETL pipeline banner."""
    print("=" * 70)
    print("  ETL Pipeline - Survey Data Processing")
    print("  Input:  Excel survey data")
    print("  Output: CSV for n8n/Retell AI workflow")
    print("=" * 70)
    print()


def print_summary(
    extract_count: int,
    transform_count: int,
    validation_report,
    output_path: Path,
    output_path_e164: Path,
    duration: float
):
    """
    Print execution summary.

    Args:
        extract_count: Number of rows extracted
        transform_count: Number of rows transformed
        validation_report: Validation report object
        output_path: Path to standard output CSV
        output_path_e164: Path to E.164 format output CSV
        duration: Execution time in seconds
    """
    print("\n" + "=" * 70)
    print("  ETL Execution Summary")
    print("=" * 70)
    print(f"  Input:  {config.INPUT_FILE.name}")
    print(f"  Output (standard): {output_path.name}")
    print(f"  Output (E.164):    {output_path_e164.name}")
    print()
    print(f"  Rows extracted:   {extract_count}")
    print(f"  Rows transformed: {transform_count}")
    print(f"  Rows validated:   {validation_report.valid_rows} / {validation_report.total_rows}")
    print()

    if validation_report.warnings:
        print("  Warnings:")
        for warning in validation_report.warnings:
            print(f"    - {warning}")
        print()

    if validation_report.errors:
        print("  Errors:")
        for error in validation_report.errors:
            print(f"    - {error}")
        print()

    print(f"  Execution time:   {duration:.2f} seconds")
    print(f"  Status:           {'SUCCESS' if not validation_report.has_errors else 'COMPLETED WITH WARNINGS'}")
    print("=" * 70)


def main():
    """Main ETL pipeline execution."""
    start_time = datetime.now()

    # Print banner
    print_banner()

    # Setup logging
    logger = setup_logger(
        name='etl',
        log_level=config.LOG_LEVEL,
        log_dir=config.LOG_DIR
    )

    logger.info("=" * 70)
    logger.info("Starting ETL pipeline")
    logger.info("=" * 70)

    try:
        # Step 1: Extract
        print("[1/6] Extracting data from Excel...")
        logger.info("Step 1: Extracting data")
        extractor = ExcelExtractor(config)
        df_raw = extractor.extract()
        logger.info(f"Extracted {len(df_raw)} rows from {config.INPUT_FILE}")
        print(f"      Extracted {len(df_raw)} rows")

        # Step 2: Transform
        print("[2/6] Transforming data...")
        logger.info("Step 2: Transforming data")
        transformer = DataTransformer(config)
        df_transformed = transformer.transform(df_raw)
        logger.info(f"Transformed {len(df_transformed)} rows")
        print(f"      Transformed {len(df_transformed)} rows")

        # Get transformation summary
        summary = transformer.get_transformation_summary(df_raw, df_transformed)
        logger.info(f"Created {summary['customer_names_created']} customer names")
        logger.info(f"Normalized {summary['phone_numbers_normalized']} phone numbers")

        # Step 3: Validate
        print("[3/6] Validating data...")
        logger.info("Step 3: Validating data")
        validator = DataValidator(config)
        validation_report = validator.validate(df_transformed)
        logger.info(f"Validation: {validation_report.valid_rows}/{validation_report.total_rows} valid rows")
        print(f"      {validation_report.valid_rows} / {validation_report.total_rows} rows passed validation")

        # Step 4: Load (two files)
        print("[4/6] Loading to CSV (standard format)...")
        logger.info("Step 4: Loading to CSV (standard format)")
        loader = CSVLoader(config)
        output_path = loader.load(df_transformed, create_backup=False)
        logger.info(f"Saved to {output_path}")
        print(f"      Saved to {output_path}")

        # Step 5: Load E.164 format (with + prefix)
        print("[5/6] Loading to CSV (E.164 format with + prefix)...")
        logger.info("Step 5: Loading to CSV (E.164 format)")
        output_path_e164 = loader.load(
            df_transformed,
            output_path=config.OUTPUT_FILE_E164,
            create_backup=False,
            e164_format=True
        )
        logger.info(f"Saved E.164 to {output_path_e164}")
        print(f"      Saved to {output_path_e164}")

        # Step 6: Verify
        print("[6/6] Verifying outputs...")
        logger.info("Step 6: Verifying outputs")
        valid_standard = loader.validate_csv(output_path)
        valid_e164 = loader.validate_csv(output_path_e164)
        if valid_standard and valid_e164:
            logger.info("CSV validation passed for both files")
            print("      CSV validation passed for both files")
        else:
            if not valid_standard:
                logger.warning(f"CSV validation failed for {output_path}")
            if not valid_e164:
                logger.warning(f"CSV validation failed for {output_path_e164}")
            print("      CSV validation failed (check logs)")

        # Calculate duration
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Print summary
        print_summary(
            extract_count=len(df_raw),
            transform_count=len(df_transformed),
            validation_report=validation_report,
            output_path=output_path,
            output_path_e164=output_path_e164,
            duration=duration
        )

        logger.info(f"ETL pipeline completed successfully in {duration:.2f} seconds")
        logger.info("=" * 70)

        return 0

    except Exception as e:
        logger.error(f"ETL pipeline failed: {e}", exc_info=True)
        print(f"\nERROR: ETL pipeline failed")
        print(f"       {e}")
        print(f"\nCheck logs for details: {config.LOG_DIR}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
