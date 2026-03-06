"""Logging setup with rotating file handler."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


def setup_logging(config: dict[str, Any], foreground: bool = False) -> logging.Logger:
    """Configure and return the application logger.

    Args:
        config: Full application config dict.
        foreground: If True, also log to console.

    Returns:
        Configured logger instance.
    """
    log_config = config["logging"]
    log_path = Path(log_config["file"])
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("file_manager")
    logger.setLevel(getattr(logging, log_config["level"].upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=log_config["max_bytes"],
        backupCount=log_config["backup_count"],
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if foreground:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
