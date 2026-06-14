from __future__ import annotations

import platform
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.core.config import BASE_DIR, BUNDLE_DIR, IS_FROZEN, resolve_runtime_path
from src.core.logs import get_log_file, read_recent_log_lines

SECRET_KEY_TERMS = ("api_key", "key", "token", "secret", "password")

PROFILE_PATHS = (
    ("assistant", "name"),
    ("assistant", "default_language"),
    ("assistant", "voice"),
    ("assistant", "personality"),
    ("voice_enabled",),
    ("voice_engine",),
    ("voice_speed",),
    ("voice_volume",),
    ("voice_gender",),
    ("voice_speaker",),
    ("language",),
    ("wake_word",),
    ("wake_words",),
    ("offline_mode",),
    ("auto_switch_mode",),
    ("privacy",),
)

SECRET_PATHS = (
    ("assistant", "yandexgpt_api_key"),
    ("weather", "api_key"),
    ("news", "api_key"),
)

CRASH_TERMS = (
    "traceback",
    "exception",
    "critical",
    "error",
    "failed",
    "ошибка",
    "исключение",
    "critical",
    "warning",
    "предупреждение",
)


def get_nested(data: dict, path: tuple[str, ...], default: Any = None) -> Any:
    node: Any = data
    for key in path:
        if not isinstance(node, dict):
            return default
        node = node.get(key, default)
    return node


def set_nested(data: dict, path: tuple[str, ...], value: Any) -> None:
    node = data
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = deepcopy(value)


def capture_assistant_profile(config: dict, label: str) -> dict:
    settings = {}
    for path in PROFILE_PATHS:
        value = get_nested(config, path)
        if value is not None:
            settings[".".join(path)] = deepcopy(value)

    return {
        "label": label.strip() or "Профиль",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "settings": settings,
    }


def apply_assistant_profile(config: dict, profile: dict) -> dict:
    updated = deepcopy(config)
    settings = profile.get("settings", {}) if isinstance(profile, dict) else {}
    if not isinstance(settings, dict):
        return updated

    for dotted_path, value in settings.items():
        path = tuple(str(dotted_path).split("."))
        if path:
            set_nested(updated, path, value)
    return updated


def make_profile_key(label: str, existing: set[str] | list[str] | tuple[str, ...]) -> str:
    base = "".join(ch.lower() if ch.isalnum() else "_" for ch in label.strip())
    base = "_".join(part for part in base.split("_") if part) or "profile"
    existing_set = set(existing)
    key = base
    index = 2
    while key in existing_set:
        key = f"{base}_{index}"
        index += 1
    return key


def redact_config(config: dict) -> dict:
    return _redact_value(deepcopy(config), ())


def redact_text(text: str, config: dict) -> str:
    redacted = str(text or "")
    for value in _collect_secret_values(config):
        if value:
            redacted = redacted.replace(value, "[скрыто]")
    return redacted


def secret_status_rows(config: dict) -> list[tuple[str, bool]]:
    labels = {
        ("assistant", "yandexgpt_api_key"): "API-ключ ЯндексGPT",
        ("weather", "api_key"): "API-ключ погоды",
        ("news", "api_key"): "API-ключ новостей",
    }
    return [(labels[path], bool(str(get_nested(config, path, "") or "").strip())) for path in SECRET_PATHS]


def clear_config_secrets(config: dict) -> dict:
    updated = deepcopy(config)
    for path in SECRET_PATHS:
        set_nested(updated, path, "")
    return updated


def format_health_snapshot(rows: list[tuple[str, str, str]]) -> str:
    labels = {"ok": "OK", "warn": "Внимание", "fail": "Ошибка"}
    return "\n".join(f"{labels.get(status, status)} | {name}: {details}" for name, status, details in rows)


def build_crash_summary(config: dict, limit: int = 80) -> str:
    lines = _collect_log_lines(config, limit=max(limit, 20) * 4)
    matched = [line for line in lines if _is_crash_line(line)]
    if not matched:
        return "За последние строки журналов критичных ошибок не найдено."
    return redact_text("\n".join(matched[-limit:]), config)


def build_diagnostic_report(
    config: dict,
    status_rows: list[tuple[str, str, str]] | None = None,
    diagnostics_output: str = "",
    history_rows: list[dict] | None = None,
) -> str:
    privacy = config.get("privacy", {}) or {}
    redact_exports = bool(privacy.get("redact_secrets_in_exports", True))
    include_logs = bool(privacy.get("include_logs_in_reports", True))
    include_history = bool(privacy.get("include_history_in_reports", False))
    crash_limit = int(privacy.get("crash_summary_lines", 80) or 80)

    def maybe_redact(text: str) -> str:
        return redact_text(text, config) if redact_exports else text

    safe_config = redact_config(config) if redact_exports else deepcopy(config)

    parts = [
        "# Отчёт поддержки Voice Assistant Cry",
        f"Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Python: {sys.version.split()[0]}",
        f"OS: {platform.platform()}",
        f"Данные пользователя: {BASE_DIR}",
        f"Ресурсы приложения: {BUNDLE_DIR}" if IS_FROZEN else f"Проект: {BUNDLE_DIR}",
        "",
        "## Health Snapshot",
        maybe_redact(format_health_snapshot(status_rows or [])),
        "",
        "## Диагностика",
        maybe_redact(diagnostics_output.strip() or "Диагностика не запускалась."),
        "",
        "## Crash Summary",
        maybe_redact(build_crash_summary(config, limit=crash_limit)),
        "",
        "## Секреты",
        "\n".join(f"{label}: {'заполнен' if present else 'не задан'}" for label, present in secret_status_rows(config)),
        "",
        "## Конфигурация без секретов" if redact_exports else "## Конфигурация",
        yaml.safe_dump(safe_config, allow_unicode=True, sort_keys=False),
    ]

    if include_logs:
        recent_logs = "\n".join(read_recent_log_lines(config, limit=80))
        parts.extend(["", "## Последние строки журнала", maybe_redact(recent_logs or "Журнал пуст.")])

    if include_history:
        history_text = yaml.safe_dump(history_rows or [], allow_unicode=True, sort_keys=False)
        parts.extend(["", "## Последние команды", maybe_redact(history_text, config)])

    return "\n".join(parts).strip() + "\n"


def write_diagnostic_report(config: dict, report_text: str, selected_path: str | Path | None = None) -> Path:
    if selected_path:
        path = Path(selected_path)
    else:
        reports_dir = resolve_runtime_path("user:data/runtime", base="user")
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / f"support_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_text, encoding="utf-8")
    return path


def _collect_secret_values(config: dict) -> list[str]:
    values = []

    def walk(node: Any, path: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, path + (str(key),))
            return
        if not _is_secret_path(path):
            return
        text = str(node or "").strip()
        if text:
            values.append(text)

    walk(config, ())
    return values


def _redact_value(value: Any, path: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {key: _redact_value(child, path + (str(key),)) for key, child in value.items()}
    if _is_secret_path(path) and str(value or "").strip():
        return "[скрыто]"
    return value


def _is_secret_path(path: tuple[str, ...]) -> bool:
    last = path[-1].lower() if path else ""
    return any(term in last for term in SECRET_KEY_TERMS)


def _collect_log_lines(config: dict, limit: int) -> list[str]:
    log_file = get_log_file(config)
    files = [log_file, log_file.parent / "assistant_stdout.log"]
    lines: list[str] = []
    for file in files:
        if not file.exists():
            continue
        try:
            file_lines = file.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        lines.extend(f"{file.name}: {line}" for line in file_lines[-limit:])
    return lines[-limit:]


def _is_crash_line(line: str) -> bool:
    lowered = line.lower()
    return any(term in lowered for term in CRASH_TERMS)
