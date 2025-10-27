from deep_translator import GoogleTranslator
import re

def translate_text(*args, **kwargs):
    """
    🌍 Универсальный переводчик для ассистента.
    Учитывает config["language"] и поддерживает 2 языка: ru, en.
    """
    config = kwargs.get("config", {})
    dataset = kwargs.get("dataset", {})
    text = kwargs.get("text", "") or " ".join(str(a) for a in args if isinstance(a, str))
    text = text.strip().lower()

    if not text:
        return "⚠️ Текст для перевода не найден."

    current_lang = config.get("language", "ru")  # язык ассистента по умолчанию

    lang_map = {
        "ru": "русский",
        "en": "английский",
    }
    name_to_code = {v: k for k, v in lang_map.items()}

    # === Определяем целевой язык ===
    target_lang = None
    for name, code in name_to_code.items():
        if re.search(fr"\bна {name}\b", text, re.IGNORECASE):
            target_lang = code
            text = re.sub(fr"\bна {name}\b", "", text, flags=re.IGNORECASE)
            break

    # Если язык не указан — выбираем автоматически
    if not target_lang or target_lang == current_lang:
        if current_lang == "ru":
            target_lang = "en"
        elif current_lang == "en":
            target_lang = "ru"
        else:
            target_lang = "en"

    # === Убираем служебные слова ===
    text = re.sub(r"\b(переведи(ть)?|перевод|translate|say|на|to)\b", "", text, flags=re.IGNORECASE)
    text = text.strip(" '\"").strip()

    if not text:
        return {
            "ru": "⚠️ Не понял, что переводить.",
            "en": "⚠️ I didn't catch what to translate.",
        }.get(current_lang, "⚠️ Error.")

    # === Перевод ===
    try:
        translated = GoogleTranslator(source="auto", target=target_lang).translate(text)

        messages = {
            "ru": f"🔤 Перевод ({lang_map.get(target_lang, target_lang)}): {translated}",
            "en": f"🔤 Translation ({lang_map.get(target_lang, target_lang)}): {translated}",
        }
        return messages.get(current_lang, translated)

    except Exception as e:
        errors = {
            "ru": f"⚠️ Ошибка при переводе: {e}",
            "en": f"⚠️ Translation error: {e}",
        }
        return errors.get(current_lang, str(e))
