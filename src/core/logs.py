from __future__ import annotations

from pathlib import Path

from src.core.config import resolve_runtime_path


def get_log_file(config: dict | None = None) -> Path:
    config = config or {}
    logging_config = config.get("logging", {}) if isinstance(config, dict) else {}
    log_dir = resolve_runtime_path(logging_config.get("dir", "data/logs"), base="user")
    return log_dir / logging_config.get("file", "assistant.log")


def read_recent_log_lines(config: dict | None = None, limit: int = 20) -> list[str]:
    log_file = get_log_file(config)
    if not log_file.exists():
        return []
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:]


def clear_log(config: dict | None = None):
    log_file = get_log_file(config)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("", encoding="utf-8")
