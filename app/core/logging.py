import logging

import structlog


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


def get_logger(*args, **kwargs):
    return structlog.get_logger(*args, **kwargs)


def request_id() -> str | None:
    return structlog.contextvars.get_contextvars().get("request_id")


def bind(**fields) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(**fields)
