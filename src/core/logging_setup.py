from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from src.core.config import resolve_runtime_path


def setup_logging(config: dict | None = None) -> Path:
    config = config or {}
    logging_config = config.get("logging", {}) if isinstance(config, dict) else {}
    log_dir = _resolve_path(logging_config.get("dir", "data/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / logging_config.get("file", "assistant.log")

    level_name = str(logging_config.get("level") or ("DEBUG" if config.get("debug") else "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=int(logging_config.get("max_bytes", 1_000_000)),
        backupCount=int(logging_config.get("backup_count", 5)),
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    return log_file


def _resolve_path(path_value: str) -> Path:
    return resolve_runtime_path(path_value, base="user")
