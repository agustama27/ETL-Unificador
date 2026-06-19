from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager


class _CallbackLogHandler(logging.Handler):
    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._callback(self.format(record))
        except Exception:
            return


@contextmanager
def bind_log_callback(callback: Callable[[str], None] | None) -> Iterator[None]:
    if callback is None:
        yield
        return

    handler = _CallbackLogHandler(callback)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield
    finally:
        root.removeHandler(handler)
