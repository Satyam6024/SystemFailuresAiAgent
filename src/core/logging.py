"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(*, json_output: bool = False, level: int = logging.INFO) -> None:
    """Set up structlog with console or JSON rendering."""

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        use_colors = sys.stderr.isatty()
        if use_colors and sys.platform == "win32":
            try:
                import colorama  # noqa: F401
            except ImportError:
                use_colors = False
        renderer = structlog.dev.ConsoleRenderer(colors=use_colors)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound logger, optionally with a name."""
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(component=name)
    return logger
