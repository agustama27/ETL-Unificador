import importlib
import sys

import pytest


class _PosixImportBlocker:
    """Meta path finder that fails ctypes.wintypes imports, as POSIX does."""

    def find_spec(self, fullname: str, path: object = None, target: object = None) -> None:
        if fullname == "ctypes.wintypes":
            raise ImportError("ctypes.wintypes is unavailable on POSIX")
        return None


def test_state_store_imports_when_wintypes_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "orchestrator.state_store", raising=False)
    monkeypatch.delitem(sys.modules, "ctypes.wintypes", raising=False)
    monkeypatch.setattr(sys, "meta_path", [_PosixImportBlocker(), *sys.meta_path])

    module = importlib.import_module("orchestrator.state_store")

    assert hasattr(module, "StateStore")
    assert "ctypes.wintypes" not in sys.modules
