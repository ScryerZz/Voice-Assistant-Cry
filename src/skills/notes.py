import re

from src.core.storage import AssistantStorage


def add_note(*args, **kwargs):
    """
    Добавляет заметку в файл.
    Извлекает текст заметки из команды пользователя.
    """
    text = kwargs.get("text", "") or " ".join(str(a) for a in args if isinstance(a, str))
    text = text.strip()
    
    if not text:
        return "Не понял, что записать."
    
    # Убираем служебные слова
    patterns = [
        "добавь заметку", "создай заметку", "запиши заметку",
        "заметка", "запиши", "добавь", "создай",
        "add note", "create note", "write note", "note"
    ]
    
    clean_text = text
    for pattern in patterns:
        clean_text = re.sub(re.escape(pattern.lower()), "", clean_text, flags=re.IGNORECASE)
    
    clean_text = clean_text.strip()
    
    if not clean_text:
        return "Не понял, что записать."
    
    try:
        storage = _storage(kwargs)
        storage.add_note(clean_text)
        return f"Заметка добавлена: {clean_text}"
    except Exception as e:
        return f"Ошибка при добавлении заметки: {e}"


def read_notes(*args, **kwargs):
    """
    Читает все заметки из файла.
    """
    try:
        storage = _storage(kwargs)
        count = storage.count_notes()
        if count == 0:
            return "Заметок пока нет."

        last_notes = storage.list_notes(limit=5)
        formatted = [f"[{note['created_at']}] {note['text']}" for note in reversed(last_notes)]
        result = f"У вас {count} заметок. Последние: " + "; ".join(formatted)
        
        return result
    except Exception as e:
        return f"Ошибка при чтении заметок: {e}"


def clear_notes(*args, **kwargs):
    """
    Удаляет все заметки.
    """
    try:
        storage = _storage(kwargs)
        count = storage.clear_notes()
        if count:
            return "Все заметки удалены."
        return "Нет заметок для удаления."
    except Exception as e:
        return f"Ошибка при удалении заметок: {e}"


def _storage(kwargs) -> AssistantStorage:
    storage = kwargs.get("storage")
    if storage:
        return storage
    config = kwargs.get("config", {}) or {}
    db_path = config.get("paths", {}).get("database")
    return AssistantStorage(db_path)
