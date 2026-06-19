from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Callable, Iterator


class _CallbackHandler(logging.Handler):
    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        self._callback(self.format(record))


@contextmanager
def bind_log_callback(log_cb: Callable[[str], None] | None) -> Iterator[None]:
    if log_cb is None:
        yield
        return

    handler = _CallbackHandler(log_cb)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    try:
        yield
    finally:
        root_logger.removeHandler(handler)
