import re
import webbrowser
from urllib.parse import quote_plus


def search_youtube(*args, **kwargs):
    """
    Ищет видео на YouTube по запросу пользователя.
    Примеры: "найди на ютубе музыку", "ютуб про python"
    """
    text = kwargs.get("text", "") or " ".join(str(a) for a in args if isinstance(a, str))
    text = text.strip().lower()
    
    if not text:
        return "⚠️ Не понял, что искать на YouTube."
    
    # Убираем служебные слова
    patterns = [
        "найди на ютубе", "ищи на ютубе", "поиск на ютубе",
        "на ютубе", "ютубе", "youtube", "ютуб",
        "найди видео", "найди", "search youtube",
        "search on youtube", "find on youtube"
    ]
    
    clean_query = text
    for pattern in patterns:
        clean_query = re.sub(re.escape(pattern.lower()), "", clean_query, flags=re.IGNORECASE)
    
    clean_query = clean_query.strip()
    
    if not clean_query:
        return "⚠️ Не понял, что искать на YouTube."
    
    try:
        # Кодируем запрос для URL
        encoded_query = quote_plus(clean_query)
        url = f"https://www.youtube.com/results?search_query={encoded_query}"
        webbrowser.open(url)
        return f"🎥 Ищу на YouTube: {clean_query}"
    except Exception as e:
        return f"❌ Ошибка при открытии YouTube: {e}"
