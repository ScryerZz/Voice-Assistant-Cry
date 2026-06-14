import re
import requests
import webbrowser
from urllib.parse import quote_plus


def search_news(*args, **kwargs):
    """
    Ищет новости по запросу и открывает в браузере.
    Использует NewsAPI (можно настроить ключ в config.yaml).
    """
    text = kwargs.get("text", "") or " ".join(str(a) for a in args if isinstance(a, str))
    config = kwargs.get("config", {})
    
    # API ключ из конфига (можно добавить в config.yaml)
    api_key = config.get("news", {}).get("api_key") or config.get("newsapi_key")
    
    # Если API ключа нет - открываем Google News
    if not api_key:
        query = _extract_query(text)
        if query:
            url = f"https://news.google.com/search?q={quote_plus(query)}"
            webbrowser.open(url)
            return f"📰 Открываю новости по запросу: {query}"
        else:
            webbrowser.open("https://news.google.com")
            return "📰 Открываю Google News"
    
    # Извлекаем тему для поиска
    query = _extract_query(text)

    try:
        if query:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "apiKey": api_key,
                "language": "ru",
                "sortBy": "publishedAt",
                "pageSize": 3,
            }
        else:
            url = "https://newsapi.org/v2/top-headlines"
            params = {
                "apiKey": api_key,
                "country": "ru",
                "pageSize": 3,
            }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            articles = data.get("articles", [])
            if not articles and not query:
                fallback_response = requests.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": "Россия",
                        "apiKey": api_key,
                        "language": "ru",
                        "sortBy": "publishedAt",
                        "pageSize": 3,
                    },
                    timeout=5,
                )
                if fallback_response.status_code == 200:
                    articles = fallback_response.json().get("articles", [])
            
            if articles:
                # Открываем первые 3 новости в браузере
                for article in articles[:3]:
                    if article.get("url"):
                        webbrowser.open(article["url"])
                
                if query:
                    return f"📰 Нашёл {_news_count_phrase(len(articles))} по запросу «{query}». Открываю топ-3."
                return f"📰 Нашёл {_news_count_phrase(len(articles))}. Открываю топ-3."
            else:
                if query:
                    return f"📰 Новостей по запросу «{query}» не найдено."
                return "📰 Свежие новости не найдены."
        
        elif response.status_code == 401:
            return "⚠️ Неверный API-ключ NewsAPI. Проверьте настройки."
        else:
            return f"⚠️ Ошибка при получении новостей (код {response.status_code})."
    
    except requests.exceptions.Timeout:
        return "⚠️ Превышено время ожидания ответа от сервера новостей."
    except requests.exceptions.ConnectionError:
        # Fallback - открываем Google News
        url = f"https://news.google.com/search?q={quote_plus(query)}"
        webbrowser.open(url)
        return f"📰 Нет подключения к NewsAPI. Открываю Google News: {query}"
    except Exception as e:
        return f"⚠️ Ошибка при получении новостей: {e}"


def _extract_query(text: str) -> str:
    """
    Извлекает тему новостей из текста команды.
    """
    if not text:
        return ""
    
    text = text.lower().strip()
    
    # Убираем служебные слова
    patterns = [
        "поищи свежие новости",
        "найди свежие новости",
        "поищи последние новости",
        "найди последние новости",
        "последние новости",
        "свежие новости",
        "поищи новости",
        "найди новости",
        "latest news",
        "search news",
        "find news",
        "что нового",
        "новостей",
        "новости",
        "news",
    ]
    
    for pattern in sorted(patterns, key=len, reverse=True):
        text = re.sub(re.escape(pattern.lower()), "", text, flags=re.IGNORECASE)
    
    # Убираем предлоги
    text = re.sub(r"\b(про|о|об|about|on)\b", "", text, flags=re.IGNORECASE)
    
    # Очищаем и возвращаем
    query = text.strip()
    
    return query


def _news_count_phrase(count: int) -> str:
    count = int(count)
    if 11 <= count % 100 <= 14:
        word = "новостей"
    elif count % 10 == 1:
        word = "новость"
    elif count % 10 in {2, 3, 4}:
        word = "новости"
    else:
        word = "новостей"
    return f"{count} {word}"

