from src.core.logs import clear_log, get_log_file, read_recent_log_lines


def log_status(*args, **kwargs):
    config = kwargs.get("config", {}) or {}
    lang = kwargs.get("lang", "ru")
    log_file = get_log_file(config)
    lines = read_recent_log_lines(config, limit=5)

    if not log_file.exists():
        return {
            "ru": "Журнал пока не создан.",
            "en": "The log file has not been created yet.",
        }.get(lang, "Журнал пока не создан.")

    errors = [line for line in lines if "[ERROR]" in line or "[WARNING]" in line]
    if lang == "en":
        return f"Log file: {log_file}. Recent warnings or errors: {len(errors)}."
    return f"Журнал находится здесь: {log_file}. В последних строках предупреждений или ошибок: {len(errors)}."


def recent_logs(*args, **kwargs):
    config = kwargs.get("config", {}) or {}
    lang = kwargs.get("lang", "ru")
    lines = read_recent_log_lines(config, limit=5)
    if not lines:
        return {
            "ru": "В журнале пока нет записей.",
            "en": "There are no log entries yet.",
        }.get(lang, "В журнале пока нет записей.")

    if lang == "en":
        return "Recent log entries: " + " | ".join(lines)
    return "Последние записи журнала: " + " | ".join(lines)


def clear_logs(*args, **kwargs):
    config = kwargs.get("config", {}) or {}
    clear_log(config)
    return {
        "ru": "Журнал очищен.",
        "en": "Log file cleared.",
    }.get(kwargs.get("lang", "ru"), "Журнал очищен.")
