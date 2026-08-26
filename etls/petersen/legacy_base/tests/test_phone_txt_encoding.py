import pandas as pd


def test_telefonos_petersen_txt_is_utf8_sig_with_bom(tmp_path):
    """
    El TXT debe escribirse en UTF-8 con BOM (utf-8-sig) para que Excel/Windows lo abra bien,
    consistente con los CSVs generados por el ETL.
    """
    from etl import write_phones_txt

    df = pd.DataFrame(
        {
            "Telefono": [
                "3437482007",          # sin prefijo
                "+5492473404055",      # ya OK
                "+542613041357",       # +54 -> +549
                "5492962423959",       # 549 sin + -> agregar +
                "542614951542",        # 54 sin + -> +549
                "",                    # vacío -> se ignora
                None,                  # None -> se ignora
                "   2644500380   ",    # espacios -> trim + prefijo
            ]
        }
    )

    out_path = tmp_path / "telefonos_petersen.txt"
    write_phones_txt(df, out_path, encoding="utf-8-sig")

    raw = out_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM

    lines = out_path.read_text(encoding="utf-8-sig").splitlines()
    assert lines == [
        "+5493437482007",
        "+5492473404055",
        "+5492613041357",
        "+5492962423959",
        "+5492614951542",
        "+5492644500380",
    ]


