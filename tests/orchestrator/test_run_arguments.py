import argparse
from pathlib import Path

import pytest

from orchestrator.run import _extra_input


def test_extra_input_parses_role_and_path() -> None:
    role, path = _extra_input("logcall=data/LOGCALL.csv")

    assert (role, path) == ("logcall", Path("data/LOGCALL.csv"))


@pytest.mark.parametrize("value", ["noequals", "=path", "role=", " = "])
def test_extra_input_rejects_malformed_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="ROLE=PATH"):
        _extra_input(value)
