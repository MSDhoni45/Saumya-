"""Logging configuration for the API.

Local dev uses plain-text output (readable in a terminal). All other
environments (staging, production) use JSON so logs can be parsed by
log aggregators (Datadog, Loki, CloudWatch, etc.).
"""

import json
import logging
import traceback
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            obj["exc"] = "".join(traceback.format_exception(*record.exc_info)).strip()
        # Any extra kwargs passed to logger.info(..., extra={...}) land here
        for key in vars(record):
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                obj[key] = getattr(record, key)
        return json.dumps(obj)


def configure_logging(*, debug: bool, environment: str) -> None:
    """Call once at startup to configure root logger."""
    handler = logging.StreamHandler()
    if environment != "local":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    root.handlers = [handler]

    # Suppress noise from chatty third-party libraries
    for noisy in ("sqlalchemy.engine", "httpx", "httpcore", "openai._base_client"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
