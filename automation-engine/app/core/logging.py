"""Structured logging — never log passwords."""

import logging
import sys

from app.config import settings


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    class RedactFilter(logging.Filter):
        SENSITIVE = ("password", "token", "secret", "credential")

        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage().lower()
            for word in self.SENSITIVE:
                if word in msg and "redact" not in msg:
                    record.msg = "[REDACTED sensitive data in log message]"
                    record.args = ()
                    break
            return True

    for handler in logging.root.handlers:
        handler.addFilter(RedactFilter())
