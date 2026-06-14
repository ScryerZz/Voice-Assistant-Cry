from __future__ import annotations

import importlib.util
import platform
from pathlib import Path


def list_capabilities(*args, **kwargs):
    dataset = kwargs.get("dataset", {}) or {}
    lang = kwargs.get("lang", "ru")
    skills = dataset.get("skills", {}) or {}

    names = []
    for key, data in skills.items():
        description = data.get("description") or key
        if key == "assistant_info":
            continue
        names.append(str(description))

    if not names:
        return {
            "ru": "Список команд пока не загружен.",
            "en": "The command list is not loaded yet.",
        }.get(lang, "Список команд пока не загружен.")

    visible = names[:10]
    if lang == "en":
        return "I can help with: " + ", ".join(visible) + "."
    return "Я умею: " + ", ".join(visible) + "."


def show_example_commands(*args, **kwargs):
    dataset = kwargs.get("dataset", {}) or {}
    lang = kwargs.get("lang", "ru")
    examples = []

    for data in (dataset.get("skills", {}) or {}).values():
        for command in data.get("commands", [])[:1]:
            patterns = command.get("patterns", [])
            if patterns:
                examples.append(str(patterns[0]))
            if len(examples) >= 8:
                break
        if len(examples) >= 8:
            break

    if not examples:
        return {
            "ru": "Примеры команд пока недоступны.",
            "en": "Command examples are not available yet.",
        }.get(lang, "Примеры команд пока недоступны.")

    if lang == "en":
        return "Try saying: " + "; ".join(examples) + "."
    return "Попробуйте сказать: " + "; ".join(examples) + "."


def run_diagnostics(*args, **kwargs):
    config = kwargs.get("config", {}) or {}
    dataset = kwargs.get("dataset", {}) or {}
    lang = kwargs.get("lang", "ru")

    checks = []
    checks.append(("Python", platform.python_version()))
    checks.append(("Команды", str(_count_commands(dataset))))
    checks.append(("Язык", config.get("assistant", {}).get("default_language", "ru")))
    checks.append(("TTS", config.get("voice_engine", "unknown")))
    checks.append(("Офлайн", "да" if config.get("offline_mode") else "нет"))
    checks.append(("AI", "включён" if config.get("assistant", {}).get("ai_enabled") else "выключен"))

    database = Path(config.get("paths", {}).get("database", "data/assistant.sqlite3"))
    checks.append(("База", "настроена" if str(database) else "не настроена"))

    missing = _missing_optional_modules(["yaml", "rapidfuzz", "requests", "sounddevice", "vosk"])
    if missing:
        checks.append(("Проблемы", "нет модулей: " + ", ".join(missing)))
    else:
        checks.append(("Проблемы", "не обнаружены"))

    if lang == "en":
        return "Diagnostics: " + "; ".join(f"{name}: {value}" for name, value in checks) + "."
    return "Диагностика: " + "; ".join(f"{name}: {value}" for name, value in checks) + "."


def _count_commands(dataset: dict) -> int:
    count = 0
    for data in (dataset.get("skills", {}) or {}).values():
        count += len(data.get("commands", []) or [])
    return count


def _missing_optional_modules(names: list[str]) -> list[str]:
    missing = []
    for name in names:
        if importlib.util.find_spec(name) is None:
            missing.append(name)
    return missing
