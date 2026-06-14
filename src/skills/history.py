from src.core.storage import AssistantStorage


def history_status(*args, **kwargs):
    storage = _storage(kwargs)
    count = storage.count_command_history()
    lang = kwargs.get("lang", "ru")
    if lang == "en":
        return f"Command history contains {count} entries."
    return f"В истории команд {count} записей."


def recent_history(*args, **kwargs):
    storage = _storage(kwargs)
    lang = kwargs.get("lang", "ru")
    rows = storage.list_command_history(limit=5)
    if not rows:
        return {
            "ru": "История команд пока пуста.",
            "en": "Command history is empty.",
        }.get(lang, "История команд пока пуста.")

    parts = []
    for row in reversed(rows):
        action = row.get("actions") or "нет действия"
        status = row.get("status") or "unknown"
        text = row.get("normalized_text") or row.get("raw_text")
        parts.append(f"{text}: {action}, {status}")

    if lang == "en":
        return "Recent commands: " + "; ".join(parts)
    return "Последние команды: " + "; ".join(parts)


def clear_history(*args, **kwargs):
    storage = _storage(kwargs)
    count = storage.clear_command_history()
    lang = kwargs.get("lang", "ru")
    if lang == "en":
        return f"Command history cleared. Removed {count} entries."
    return f"История команд очищена. Удалено записей: {count}."


def _storage(kwargs) -> AssistantStorage:
    storage = kwargs.get("storage")
    if storage:
        return storage
    config = kwargs.get("config", {}) or {}
    return AssistantStorage(config.get("paths", {}).get("database"))
