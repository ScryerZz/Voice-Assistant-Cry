import re
from pathlib import Path
from datetime import datetime

NOTES_FILE = Path("data/notes.txt")


def add_note(*args, **kwargs):
    """
    Добавляет заметку в файл.
    Извлекает текст заметки из команды пользователя.
    """
    text = kwargs.get("text", "") or " ".join(str(a) for a in args if isinstance(a, str))
    text = text.strip().lower()
    
    if not text:
        return "⚠️ Не понял, что записать."
    
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
        return "⚠️ Не понял, что записать."
    
    try:
        NOTES_FILE.parent.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {clean_text}\n")
        return f"✅ Заметка добавлена: {clean_text}"
    except Exception as e:
        return f"❌ Ошибка при добавлении заметки: {e}"


def read_notes(*args, **kwargs):
    """
    Читает все заметки из файла.
    """
    try:
        if not NOTES_FILE.exists():
            return "📝 Заметок пока нет."
        
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        
        if not content:
            return "📝 Заметок пока нет."
        
        lines = content.split("\n")
        count = len(lines)
        
        # Возвращаем последние 5 заметок для озвучки
        last_notes = lines[-5:]
        result = f"📝 У вас {count} заметок. Последние: " + "; ".join(last_notes)
        
        return result
    except Exception as e:
        return f"❌ Ошибка при чтении заметок: {e}"


def clear_notes(*args, **kwargs):
    """
    Удаляет все заметки.
    """
    try:
        if NOTES_FILE.exists():
            NOTES_FILE.unlink()
            return "🗑️ Все заметки удалены."
        return "📝 Нет заметок для удаления."
    except Exception as e:
        return f"❌ Ошибка при удалении заметок: {e}"
