import re
import sys

from src.core.config import get_settings

def _detect_lang_from_text(text: str):
    if not text:
        return None
    t = text.lower()
    mapping = {
        "русский": "ru", "русски": "ru", "russian": "ru", "ru": "ru", "ru-ru": "ru",
        "английский": "en", "англиский": "en", "english": "en", "en": "en", "en-us": "en"
    }
    for token in re.split(r"[\s,\.]+", t):
        if token in mapping:
            return mapping[token]
    m = re.search(r"\b([a-z]{2})(?:[-_][A-Z]{2})?\b", t)
    if m:
        code = m.group(1).lower()
        return mapping.get(code, code)
    return None

def _recognition_language(lang: str) -> str:
    return {"ru": "ru-RU", "en": "en-US"}.get(lang, lang)

def change_language(*args, **kwargs):
    """
    Skills handler for 'change language' command.
    Uses central settings (get_settings()) instead of manual file access.
    Expects kwargs.get('text') with user phrase.
    Optionally in kwargs: recognizer, tts — will be updated if present.
    Returns localized confirmation string.
    """
    text = kwargs.get("text", "") or " ".join(str(a) for a in args if isinstance(a, str))
    lang = _detect_lang_from_text(text)
    if not lang:
        return {
            "ru": "Какой язык установить? (русский, английский)",
            "en": "Which language to set? (russian, english)"
        }.get(kwargs.get("lang", "ru"), "Какой язык установить?")

    # Обновляем runtime-объекты, если переданы
    recognizer = kwargs.get("recognizer")
    tts = kwargs.get("tts")

    try:
        if recognizer and hasattr(recognizer, "set_language"):
            recognizer.set_language(lang)
        if tts and hasattr(tts, "set_language"):
            tts.set_language(lang)
    except Exception:
        pass

    # Обновляем config.yaml через центральный Settings API.
    try:
        settings = get_settings()
        settings.set("assistant", "default_language", value=lang)
        settings.set("language", value=_recognition_language(lang))
        settings.save()
    except Exception as exc:
        return f"Не удалось сохранить язык: {exc}"

    messages = {
        "ru": "Язык обновлён.",
        "en": "Language updated."
    }
    return messages.get(lang, messages["ru"])
def shutdown_assistant(*args, **kwargs):
    """
    🛑 Корректно завершает работу Cry.

    В kwargs можно передавать:
      - context: { "workers": [...], "assistant_name": str }
      - query: исходная команда пользователя
    """

    if kwargs.get("chat_mode"):
        return "В чате эта команда не закрывает окно настроек. Для остановки голосового ассистента используйте кнопку Остановить."

    context = kwargs.get("context", {})
    query = kwargs.get("query") or kwargs.get("text", "")
    config = kwargs.get("config", {}) or context.get("config", {}) or {}
    assistant_name = (
        context.get("assistant_name")
        or config.get("assistant", {}).get("name")
        or "Cry"
    )
    workers = kwargs.get("workers") or context.get("workers", [])
    recognizer = kwargs.get("recognizer") or context.get("recognizer")

    print(f"🧠 {assistant_name} получил команду завершения: {query}")
    print("🔻 Завершение активных процессов...")

    for w in workers:
        if hasattr(w, "stop"):
            try:
                w.stop()
                print(f"✅ Остановлен поток: {getattr(w, 'name', 'Unnamed')}")
            except Exception as e:
                print(f"⚠️ Не удалось остановить поток: {e}")

    if recognizer and hasattr(recognizer, "stop"):
        recognizer.stop()

    print(f"👋 {assistant_name} завершает работу.")
    sys.exit(0)
