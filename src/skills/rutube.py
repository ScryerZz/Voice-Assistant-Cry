import re
import webbrowser
from urllib.parse import quote_plus


def search_rutube(*args, **kwargs):
    """
    Ищет видео на Rutube по запросу пользователя.
    Старые фразы про YouTube оставлены как совместимые алиасы.
    """
    text = kwargs.get("text", "") or " ".join(str(a) for a in args if isinstance(a, str))
    text = text.strip().lower()

    if not text:
        return "Не понял, что искать на Rutube."

    patterns = [
        "найди на рутубе", "ищи на рутубе", "поиск на рутубе",
        "найди в рутубе", "ищи в рутубе", "на рутубе",
        "рутубе", "rutube", "рутуб",
        "найди на ютубе", "ищи на ютубе", "поиск на ютубе",
        "на ютубе", "ютубе", "youtube", "ютуб",
        "найди видео", "найди", "search youtube",
        "search on youtube", "find on youtube",
        "search rutube", "search on rutube", "find on rutube",
    ]

    clean_query = text
    for pattern in patterns:
        clean_query = re.sub(re.escape(pattern.lower()), "", clean_query, flags=re.IGNORECASE)

    clean_query = clean_query.strip()

    if not clean_query:
        return "Не понял, что искать на Rutube."

    try:
        encoded_query = quote_plus(clean_query)
        url = f"https://rutube.ru/search/?query={encoded_query}"
        webbrowser.open(url)
        return f"Ищу на Rutube: {clean_query}"
    except Exception as exc:
        return f"Ошибка при открытии Rutube: {exc}"
