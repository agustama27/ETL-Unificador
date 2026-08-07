from __future__ import annotations

import csv
import importlib.util
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable, Iterator


REQUIRED_FIXTURE_FILES = ("input.csv", "expected.csv", "assertions.json")


@dataclass(frozen=True)
class CountryConfig:
    name: str
    generator_path: Path
    expected_filename_regex: str
    key_column: str


@dataclass(frozen=True)
class FixtureCase:
    country: str
    case_name: str
    input_csv: Path
    expected_csv: Path
    assertions_json: Path


BASE_DIR = Path(__file__).resolve().parents[2]
COUNTRY_CONFIGS: dict[str, CountryConfig] = {
    "argentina": CountryConfig(
        name="argentina",
        generator_path=BASE_DIR / "base_argentina" / "procesos" / "base_generator.py",
        expected_filename_regex=r"^SOCIAL_ARG_CARTERA_[0-9]{8}\\.csv$",
        key_column="documento",
    ),
    "chile": CountryConfig(
        name="chile",
        generator_path=BASE_DIR / "base_chile" / "procesos" / "base_generator.py",
        expected_filename_regex=r"^SOCIAL_CHI_CARTERA_[0-9]{8}\\.csv$",
        key_column="rut",
    ),
}


def discover_cases(fixtures_root: Path, country_filter: str | None = None) -> list[FixtureCase]:
    if not fixtures_root.exists():
        raise FileNotFoundError(f"Fixtures root not found: {fixtures_root}")

    if country_filter is not None:
        country_name = country_filter.lower().strip()
        if country_name not in COUNTRY_CONFIGS:
            supported = ", ".join(sorted(COUNTRY_CONFIGS))
            raise ValueError(f"Unknown country '{country_filter}'. Supported: {supported}")
        countries = [country_name]
    else:
        countries = sorted(COUNTRY_CONFIGS)

    cases: list[FixtureCase] = []
    for country in countries:
        country_dir = fixtures_root / country
        if not country_dir.exists() or not country_dir.is_dir():
            raise FileNotFoundError(
                f"Missing fixture directory for country '{country}': {country_dir}"
            )

        case_dirs = sorted(path for path in country_dir.iterdir() if path.is_dir())
        for case_dir in case_dirs:
            missing_files = [
                filename for filename in REQUIRED_FIXTURE_FILES if not (case_dir / filename).is_file()
            ]
            if missing_files:
                missing = ", ".join(missing_files)
                raise FileNotFoundError(
                    f"Missing fixture files for {country}/{case_dir.name}: {missing}"
                )

            cases.append(
                FixtureCase(
                    country=country,
                    case_name=case_dir.name,
                    input_csv=case_dir / "input.csv",
                    expected_csv=case_dir / "expected.csv",
                    assertions_json=case_dir / "assertions.json",
                )
            )

    if not cases:
        raise FileNotFoundError(f"No fixture cases found under: {fixtures_root}")

    return cases


def load_generate_base(generator_path: Path) -> Callable[..., Path]:
    if not generator_path.is_file():
        raise FileNotFoundError(f"Generator module not found: {generator_path}")

    module_name = f"smoke_generator_{generator_path.parent.parent.name}"
    spec = importlib.util.spec_from_file_location(module_name, generator_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec for: {generator_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return _extract_generate_base(module, generator_path)


def _extract_generate_base(module: ModuleType, generator_path: Path) -> Callable[..., Path]:
    generate_base = getattr(module, "generate_base", None)
    if not callable(generate_base):
        raise AttributeError(f"Module does not expose callable generate_base(): {generator_path}")
    return generate_base


@contextmanager
def execute_case_generation(
    case: FixtureCase,
    country_config: CountryConfig,
) -> Iterator[Path]:
    generate_base = load_generate_base(country_config.generator_path)
    with tempfile.TemporaryDirectory(prefix=f"smoke-{case.country}-{case.case_name}-") as temp_dir:
        output_path = Path(temp_dir) / "generated.csv"
        generated = Path(generate_base(input_path=case.input_csv, output_path=output_path))
        if not generated.is_file():
            raise FileNotFoundError(
                f"Generator did not produce output for {case.country}/{case.case_name}: {generated}"
            )
        yield generated


def normalize_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    text = path.read_text(encoding="utf-8-sig")
    delimiter = _detect_delimiter(text)

    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, delimiter=delimiter)
        rows = list(reader)

    if not rows:
        raise ValueError(f"CSV has no rows: {path}")

    headers = [_normalize_cell(header) for header in rows[0]]
    normalized_rows: list[dict[str, str]] = []
    for row in rows[1:]:
        normalized_row = [_normalize_cell(value) for value in row]
        if len(normalized_row) < len(headers):
            normalized_row.extend([""] * (len(headers) - len(normalized_row)))
        elif len(normalized_row) > len(headers):
            normalized_row = normalized_row[: len(headers)]
        normalized_rows.append(dict(zip(headers, normalized_row)))

    return headers, normalized_rows


def _detect_delimiter(sample_text: str) -> str:
    if not sample_text:
        return ";"

    try:
        dialect = csv.Sniffer().sniff(sample_text[:4096], delimiters=",;")
        return dialect.delimiter
    except csv.Error:
        return ";"


def _normalize_cell(value: str) -> str:
    return (value or "").replace("\x00", "").strip()
