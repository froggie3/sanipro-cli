import logging
import typing

logger = logging.getLogger(__name__)


class BufferingLoggerWriter(typing.IO):
    """Pseudo file object redirected to logger."""

    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.level = level
        self.buffer = ""

    def write(self, message) -> int:
        if "\n" not in message:
            self.buffer += message
        else:
            parts = message.split("\n")
            if self.buffer:
                s = self.buffer + parts.pop(0)
                self.logger.log(self.level, s)
            self.buffer = parts.pop()
            for part in parts:
                self.logger.log(self.level, part)
        return 0

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


__debug_fp = BufferingLoggerWriter(logger, logging.DEBUG)


def get_log_level_from(count: int | None) -> int:
    """Map function that maps the number of options to log level."""
    import logging

    if count is None:
        return logging.INFO
    elif count == 0:
        return logging.INFO
    elif count == 1:
        return logging.INFO
    elif count == 2:
        return logging.DEBUG
    else:
        raise ValueError


def get_debug_fp() -> BufferingLoggerWriter:
    """Get `BufferingLoggerWriter` instance. Mainly for `pprint.pprint()`."""
    return __debug_fp