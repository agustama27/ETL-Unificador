"""Tests del contrato de carpetas fechadas y límites del CLI."""

from datetime import date
from pathlib import Path

import pytest

import main
from scripts import generate_sample_data
from src.etl.config import PipelineConfig


def _write_required_inputs(input_dir: Path) -> None:
    input_dir.mkdir(parents=True)
    for filename in ("saldos.xls", "maquinarias.xlsx", "repuestos.pdf", "servicios.xlsx"):
        (input_dir / filename).write_text("fixture", encoding="utf-8")


def test_for_dated_run_uses_default_sources_and_partitioned_outputs(tmp_path: Path) -> None:
    run_date = date(2026, 8, 4)
    _write_required_inputs(tmp_path / "inputs" / run_date.isoformat())

    config = PipelineConfig.for_dated_run(
        project_root=tmp_path,
        run_date=run_date,
        source_names={},
        reference_date=date(2026, 7, 31),
        overwrite=False,
    )

    assert config.saldos_generales_path == tmp_path / "inputs" / "2026-08-04" / "saldos.xls"
    assert config.maquinarias_path == tmp_path / "inputs" / "2026-08-04" / "maquinarias.xlsx"
    assert config.remitos_repuestos_path == tmp_path / "inputs" / "2026-08-04" / "repuestos.pdf"
    assert config.remitos_servicios_path == tmp_path / "inputs" / "2026-08-04" / "servicios.xlsx"
    assert config.output_dir == tmp_path / "outputs" / "2026-08-04"
    assert config.run_date == run_date
    assert config.reference_date == date(2026, 7, 31)


def test_for_dated_run_uses_the_selected_partition(tmp_path: Path) -> None:
    run_date = date(2027, 1, 2)
    _write_required_inputs(tmp_path / "inputs" / run_date.isoformat())

    config = PipelineConfig.for_dated_run(
        project_root=tmp_path,
        run_date=run_date,
        source_names={},
        reference_date=date(2026, 12, 31),
        overwrite=True,
    )

    assert config.saldos_generales_path.parent == tmp_path / "inputs" / "2027-01-02"
    assert config.output_dir == tmp_path / "outputs" / "2027-01-02"
    assert config.overwrite is True


def test_for_dated_run_accepts_separate_input_and_output_dates(tmp_path: Path) -> None:
    input_date = date(2026, 8, 4)
    output_date = date(2026, 8, 12)
    _write_required_inputs(tmp_path / "inputs" / input_date.isoformat())

    config = PipelineConfig.for_dated_run(
        project_root=tmp_path,
        input_date=input_date,
        output_date=output_date,
        source_names={},
        reference_date=date(2026, 7, 31),
        overwrite=False,
    )

    assert config.saldos_generales_path.parent == tmp_path / "inputs" / "2026-08-04"
    assert config.output_dir == tmp_path / "outputs" / "2026-08-12"
    assert config.run_date == output_date


@pytest.mark.parametrize(
    ("run_date", "filename"),
    [(date(2026, 8, 4), "cierre.xlsx"), (date(2027, 1, 2), "actualizado.xlsx")],
)
def test_for_dated_run_selects_valid_overrides_inside_the_dated_input_root(
    tmp_path: Path, run_date: date, filename: str
) -> None:
    input_dir = tmp_path / "inputs" / run_date.isoformat()
    _write_required_inputs(input_dir)
    (input_dir / "maquinarias.xlsx").unlink()
    override = input_dir / filename
    override.write_text("fixture", encoding="utf-8")

    config = PipelineConfig.for_dated_run(
        project_root=tmp_path,
        run_date=run_date,
        source_names={"maquinarias": override.name},
        reference_date=date(2026, 7, 31),
        overwrite=False,
    )

    assert config.maquinarias_path == override
    assert config.maquinarias_path.parent == input_dir


@pytest.mark.parametrize("filename", ["cierre.csv", "CIERRE.CSV"])
def test_for_dated_run_accepts_csv_saldos_overrides_inside_the_partition(
    tmp_path: Path, filename: str
) -> None:
    run_date = date(2026, 8, 4)
    input_dir = tmp_path / "inputs" / run_date.isoformat()
    _write_required_inputs(input_dir)
    (input_dir / "saldos.xls").unlink()
    override = input_dir / filename
    override.write_bytes(b"fixture")

    config = PipelineConfig.for_dated_run(
        project_root=tmp_path,
        run_date=run_date,
        source_names={"saldos": filename},
        reference_date=date(2026, 7, 31),
        overwrite=False,
    )

    assert config.saldos_generales_path == override


def test_for_dated_run_rejects_xlsx_saldos_override_before_extraction(tmp_path: Path) -> None:
    run_date = date(2026, 8, 4)
    input_dir = tmp_path / "inputs" / run_date.isoformat()
    _write_required_inputs(input_dir)
    (input_dir / "saldos.xlsx").write_bytes(b"not-an-accepted-saldos-source")

    with pytest.raises(ValueError, match="saldos: nombre de archivo inválido"):
        PipelineConfig.for_dated_run(
            project_root=tmp_path,
            run_date=run_date,
            source_names={"saldos": "saldos.xlsx"},
            reference_date=date(2026, 7, 31),
            overwrite=False,
        )


@pytest.mark.parametrize(
    ("role", "filename"),
    [("saldos", "../saldos.xls"), ("repuestos", "repuestos.xlsx")],
)
def test_for_dated_run_rejects_unsafe_or_wrong_suffix_source_names(
    tmp_path: Path, role: str, filename: str
) -> None:
    run_date = date(2026, 8, 4)
    _write_required_inputs(tmp_path / "inputs" / run_date.isoformat())

    with pytest.raises(ValueError, match=role):
        PipelineConfig.for_dated_run(
            project_root=tmp_path,
            run_date=run_date,
            source_names={role: filename},
            reference_date=date(2026, 7, 31),
            overwrite=False,
        )


def test_for_dated_run_aggregates_invalid_input_roles(tmp_path: Path) -> None:
    run_date = date(2026, 8, 4)
    input_dir = tmp_path / "inputs" / run_date.isoformat()
    input_dir.mkdir(parents=True)
    (input_dir / "saldos.xls").write_text("fixture", encoding="utf-8")
    (input_dir / "maquinarias.xlsx").mkdir()

    with pytest.raises(ValueError) as error:
        PipelineConfig.for_dated_run(
            project_root=tmp_path,
            run_date=run_date,
            source_names={},
            reference_date=date(2026, 7, 31),
            overwrite=False,
        )

    message = str(error.value)
    assert "maquinarias" in message
    assert "repuestos" in message
    assert "servicios" in message


def test_for_dated_run_rejects_a_symlink_escaping_the_input_partition(
    tmp_path: Path,
) -> None:
    run_date = date(2026, 8, 4)
    input_dir = tmp_path / "inputs" / run_date.isoformat()
    _write_required_inputs(input_dir)
    outside_source = tmp_path / "outside.xls"
    outside_source.write_text("fixture", encoding="utf-8")
    try:
        (input_dir / "saldos.xls").unlink()
        (input_dir / "saldos.xls").symlink_to(outside_source)
    except OSError:
        pytest.skip("El entorno no permite crear symlinks para validar contención")

    with pytest.raises(ValueError, match="saldos"):
        PipelineConfig.for_dated_run(
            project_root=tmp_path,
            run_date=run_date,
            source_names={},
            reference_date=date(2026, 7, 31),
            overwrite=False,
        )


def test_parse_args_keeps_run_date_and_reference_date_independent() -> None:
    args = main._parse_args(
        [
            "--tipo-cambio",
            "1250.50",
            "--run-date",
            "2026-08-04",
            "--reference-date",
            "2026-07-31",
        ]
    )

    assert args.run_date == date(2026, 8, 4)
    assert args.reference_date == date(2026, 7, 31)


def test_parse_args_accepts_separate_input_and_output_dates() -> None:
    args = main._parse_args(["--input-date", "2026-08-04", "--output-date", "2026-08-12"])

    assert args.input_date == date(2026, 8, 4)
    assert args.output_date == date(2026, 8, 12)


def test_parse_args_allows_omitting_deprecated_exchange_rate() -> None:
    assert main._parse_args([]).tipo_cambio is None


def test_parse_args_accepts_a_valid_deprecated_exchange_rate() -> None:
    assert main._parse_args(["--tipo-cambio", "1250.50"]).tipo_cambio == 1250.50


def test_main_warns_for_legacy_exchange_rate_without_passing_it_to_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: dict[str, object] = {}
    parsed_args = main._parse_args(["--tipo-cambio", "1"])

    def fake_config(**kwargs):
        captured.update(kwargs)
        # Doble mínimo de PipelineConfig: main imprime qué archivo entró como
        # qué fuente antes de procesar, así que necesita las cuatro rutas.
        return type(
            "ConfigDoble",
            (),
            {
                "saldos_generales_path": Path("saldos.xls"),
                "maquinarias_path": Path("maquinarias.xlsx"),
                "remitos_repuestos_path": Path("repuestos.pdf"),
                "remitos_servicios_path": Path("servicios.xlsx"),
            },
        )()

    monkeypatch.setattr(
        main.PipelineConfig,
        "for_dated_run",
        classmethod(lambda cls, **kwargs: fake_config(**kwargs)),
    )
    monkeypatch.setattr(
        main,
        "run_pipeline",
        lambda config: type("Result", (), {"roman_path": "roman", "approach_path": "approach", "diagnostics": type("D", (), {"summary": lambda self: "ARS excluidos: fuente=0"})()})(),
    )
    monkeypatch.setattr(main, "_parse_args", lambda: parsed_args)

    main.main()

    assert "tipo_cambio_usd" not in captured
    assert "obsoleto y no tiene efecto" in capsys.readouterr().out


def test_valid_legacy_rates_produce_identical_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_date = date(2026, 8, 4)
    generate_sample_data.generate_sample_data(tmp_path, run_date)
    config = PipelineConfig.for_dated_run(
        project_root=tmp_path,
        run_date=run_date,
        source_names={},
        reference_date=date(2026, 7, 28),
        overwrite=False,
    )
    outputs: list[tuple[bytes, bytes]] = []
    configs = iter(
        [
            config,
            PipelineConfig(
                saldos_generales_path=config.saldos_generales_path,
                maquinarias_path=config.maquinarias_path,
                remitos_repuestos_path=config.remitos_repuestos_path,
                remitos_servicios_path=config.remitos_servicios_path,
                output_dir=config.output_dir.parent / "second-output",
                reference_date=config.reference_date,
                run_date=config.run_date,
            ),
        ]
    )
    original_parse_args = main._parse_args

    monkeypatch.setattr(
        main.PipelineConfig,
        "for_dated_run",
        classmethod(lambda cls, **kwargs: next(configs)),
    )
    for rate in ("1", "1250.50"):
        monkeypatch.setattr(
            main,
            "_parse_args",
            lambda rate=rate: original_parse_args(["--tipo-cambio", rate]),
        )
        main.main()
        current = (
            config.output_dir
            if rate == "1"
            else config.output_dir.parent / "second-output"
        )
        outputs.append(
            (
                next(current.glob("ALVAREZ_MAQUINARIAS_ROMAN_*.csv")).read_bytes(),
                next(current.glob("ALVAREZ_MAQUINARIAS_E1KIA_*.csv")).read_bytes(),
            )
        )

    assert outputs[0] == outputs[1]


def test_invalid_legacy_rate_does_not_replace_existing_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    roman = output_dir / "ALVAREZ_MAQUINARIAS_ROMAN_260804.csv"
    approach = output_dir / "ALVAREZ_MAQUINARIAS_E1KIA_260804.csv"
    roman.write_bytes(b"existing-roman")
    approach.write_bytes(b"existing-approach")
    original_parse_args = main._parse_args

    monkeypatch.setattr(main, "_parse_args", lambda: original_parse_args(["--tipo-cambio", "0"]))
    monkeypatch.setattr(main, "run_pipeline", lambda config: pytest.fail("pipeline should not run"))

    with pytest.raises(SystemExit) as error:
        main.main()

    assert error.value.code == 2
    assert roman.read_bytes() == b"existing-roman"
    assert approach.read_bytes() == b"existing-approach"


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_parse_args_rejects_invalid_deprecated_exchange_rate(value: str) -> None:
    with pytest.raises(SystemExit) as error:
        main._parse_args(["--tipo-cambio", value])
    assert error.value.code == 2


@pytest.mark.parametrize("invalid_date", ["2026-02-30", "2026-8-4"])
def test_parse_args_rejects_invalid_run_dates(invalid_date: str) -> None:
    with pytest.raises(SystemExit) as error:
        main._parse_args(
            ["--tipo-cambio", "1250.50", "--run-date", invalid_date]
        )

    assert error.value.code == 2


def test_parse_args_uses_bare_source_names_and_allows_valid_override() -> None:
    args = main._parse_args(
        ["--tipo-cambio", "1250.50", "--maquinarias", "cierre.xlsx"]
    )

    assert args.saldos == "saldos.xls"
    assert args.maquinarias == "cierre.xlsx"
    assert args.repuestos == "repuestos.pdf"
    assert args.servicios == "servicios.xlsx"


def test_saldos_help_documents_the_default_xls_and_supported_csv_override(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main._parse_args(["--help"])

    assert error.value.code == 0
    help_text = capsys.readouterr().out
    assert "saldos.xls" in help_text
    assert "saldos.csv" in help_text


@pytest.mark.parametrize(
    "argument",
    [
        ["--saldos", "data/raw/saldos.xls"],
        ["--output", "elsewhere"],
    ],
)
def test_parse_args_rejects_legacy_paths_and_output_override(argument: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main._parse_args(["--tipo-cambio", "1250.50", *argument])

    assert error.value.code == 2


@pytest.mark.parametrize("run_date", [date(2026, 8, 4), date(2027, 1, 2)])
def test_sample_generator_writes_fixed_source_names_to_dated_input_partition(
    tmp_path: Path, run_date: date
) -> None:
    generated_dir = generate_sample_data.generate_sample_data(tmp_path, run_date)

    assert generated_dir == tmp_path / "inputs" / run_date.isoformat()
    assert {path.name for path in generated_dir.iterdir()} == {
        "saldos.xls",
        "maquinarias.xlsx",
        "repuestos.pdf",
        "servicios.xlsx",
    }


def test_gitignore_protects_dated_customer_data_and_exports() -> None:
    ignored_patterns = (Path(main.__file__).resolve().parent / ".gitignore").read_text(
        encoding="utf-8"
    )

    assert "inputs/" in ignored_patterns
    assert "outputs/" in ignored_patterns


@pytest.mark.parametrize(
    "guide", ["README.md", "docs/HARNESS.md", "docs/SPEC.md", "docs/ASSUMPTIONS.md"]
)
def test_operator_guides_document_the_dated_io_contract(guide: str) -> None:
    project_root = Path(main.__file__).resolve().parent
    content = (project_root / guide).read_text(encoding="utf-8")
    normalized_content = " ".join(content.split())

    assert "inputs/<run-date>/" in content
    assert "--run-date" in content
    assert "--overwrite" in content
    assert "--output data/output" not in content
    assert "bds/" not in content
    assert "Los ejemplos son genéricos." in normalized_content
    assert (
        "No documente datos de clientes ni detalles operativos específicos."
        in normalized_content
    )


@pytest.mark.parametrize("guide", ["README.md", "docs/SPEC.md"])
def test_operator_guides_name_the_fixed_exports(guide: str) -> None:
    project_root = Path(main.__file__).resolve().parent
    content = (project_root / guide).read_text(encoding="utf-8")

    assert "ALVAREZ_MAQUINARIAS_ROMAN_YYMMDD.csv" in content
    assert "ALVAREZ_MAQUINARIAS_E1KIA_YYMMDD.csv" in content


@pytest.mark.parametrize("guide", ["README.md", "docs/SPEC.md", "docs/ASSUMPTIONS.md"])
def test_operator_guides_document_the_strict_saldos_csv_contract(guide: str) -> None:
    project_root = Path(main.__file__).resolve().parent
    content = (project_root / guide).read_text(encoding="utf-8")

    assert "CP1252" in content
    assert "coma" in content
    assert "--saldos" in content
    assert "saldos.xls" in content
    assert "saldos.csv" in content
    assert "sin salidas parciales" in content


def _write_autologica_inputs(input_dir: Path) -> dict[str, str]:
    """Los exports tal como los manda Autologica: nombres sin convención."""
    nombres = {
        "saldos": "saldos Agosto.csv",
        "maquinarias": "maquinarias 12-08.xlsx",
        "repuestos": "REMITOS - REPUESTOS (4).pdf",
        "servicios": "Remitos - Servicios. 12-08.xlsx",
    }
    input_dir.mkdir(parents=True, exist_ok=True)
    for nombre in nombres.values():
        (input_dir / nombre).write_text("fixture", encoding="utf-8")
    return nombres


def test_for_dated_run_identifica_los_exports_de_autologica_por_extension(
    tmp_path: Path,
) -> None:
    """El operador deja los cuatro archivos con el nombre que vinieron y no
    tiene que renombrar nada: cada fuente se reconoce por su extensión."""
    run_date = date(2026, 8, 19)
    nombres = _write_autologica_inputs(tmp_path / "inputs" / run_date.isoformat())

    config = PipelineConfig.for_dated_run(
        project_root=tmp_path,
        run_date=run_date,
        source_names={},
        reference_date=date(2026, 8, 19),
        overwrite=False,
    )

    assert config.saldos_generales_path.name == nombres["saldos"]
    assert config.maquinarias_path.name == nombres["maquinarias"]
    assert config.remitos_repuestos_path.name == nombres["repuestos"]
    assert config.remitos_servicios_path.name == nombres["servicios"]


def test_los_nombres_canonicos_tienen_precedencia_sobre_el_descubrimiento(
    tmp_path: Path,
) -> None:
    """Una partición que ya usa la convención no cambia de comportamiento
    aunque haya otros archivos con la misma extensión."""
    run_date = date(2026, 8, 19)
    input_dir = tmp_path / "inputs" / run_date.isoformat()
    _write_required_inputs(input_dir)
    (input_dir / "maquinarias viejo.xlsx").write_text("fixture", encoding="utf-8")

    config = PipelineConfig.for_dated_run(
        project_root=tmp_path,
        run_date=run_date,
        source_names={},
        reference_date=date(2026, 8, 19),
        overwrite=False,
    )

    assert config.maquinarias_path.name == "maquinarias.xlsx"
    assert config.remitos_servicios_path.name == "servicios.xlsx"


def test_el_nombre_indicado_por_el_operador_le_gana_al_descubrimiento(
    tmp_path: Path,
) -> None:
    run_date = date(2026, 8, 19)
    input_dir = tmp_path / "inputs" / run_date.isoformat()
    _write_autologica_inputs(input_dir)
    (input_dir / "cierre.csv").write_text("fixture", encoding="utf-8")

    config = PipelineConfig.for_dated_run(
        project_root=tmp_path,
        run_date=run_date,
        source_names={"saldos": "cierre.csv"},
        reference_date=date(2026, 8, 19),
        overwrite=False,
    )

    assert config.saldos_generales_path.name == "cierre.csv"


@pytest.mark.parametrize(
    ("extra", "roles_ambiguos"),
    [
        ("otro.pdf", ["repuestos"]),
        ("otro.csv", ["saldos"]),
        ("otro.xlsx", ["maquinarias"]),
    ],
)
def test_el_descubrimiento_aborta_en_vez_de_elegir_entre_dos_candidatos(
    tmp_path: Path, extra: str, roles_ambiguos: list[str]
) -> None:
    """Dos archivos compiten por la misma fuente: se aborta nombrando lo que
    había. Elegir uno al azar metería datos del día equivocado en el ROMAN."""
    run_date = date(2026, 8, 19)
    input_dir = tmp_path / "inputs" / run_date.isoformat()
    _write_autologica_inputs(input_dir)
    (input_dir / extra).write_text("fixture", encoding="utf-8")

    with pytest.raises(ValueError) as error:
        PipelineConfig.for_dated_run(
            project_root=tmp_path,
            run_date=run_date,
            source_names={},
            reference_date=date(2026, 8, 19),
            overwrite=False,
        )

    message = str(error.value)
    for role in roles_ambiguos:
        assert f"{role}: no se pudo identificar" in message
    assert extra in message  # el error lista la partición para poder actuar


def test_una_particion_de_entrada_inexistente_se_explica_y_sugiere_prepararla(
    tmp_path: Path,
) -> None:
    run_date = date(2026, 8, 19)

    with pytest.raises(ValueError, match="No existe la partición de entrada"):
        PipelineConfig.for_dated_run(
            project_root=tmp_path,
            run_date=run_date,
            source_names={},
            reference_date=date(2026, 8, 19),
            overwrite=False,
        )


def test_preparar_crea_la_particion_del_dia_y_es_idempotente(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_date = date(2026, 8, 19)
    esperada = tmp_path / "inputs" / run_date.isoformat()

    main._preparar_particion(tmp_path, run_date)
    assert esperada.is_dir()
    assert "2026-08-19" in capsys.readouterr().out

    (esperada / "saldos Agosto.csv").write_text("fixture", encoding="utf-8")
    main._preparar_particion(tmp_path, run_date)

    salida = capsys.readouterr().out
    assert "ya existía" in salida
    assert "saldos Agosto.csv" in salida


def test_parse_args_expone_preparar_sin_afectar_los_defaults() -> None:
    assert main._parse_args(["--preparar"]).preparar is True
    assert main._parse_args([]).preparar is False
