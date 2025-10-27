import re
import requests
from datetime import datetime


def get_weather(*args, **kwargs):
    """
    Получает погоду для указанного города через OpenWeatherMap API.
    Примеры: "погода в Москве", "какая погода в Казани"
    """
    text = kwargs.get("text", "") or " ".join(str(a) for a in args if isinstance(a, str))
    config = kwargs.get("config", {})
    
    # API ключ из конфига (можно добавить в config.yaml)
    api_key = config.get("weather", {}).get("api_key") or config.get("openweather_api_key")
    
    # Если API ключа нет - возвращаем статический ответ
    if not api_key:
        return "⚠️ API ключ OpenWeatherMap не настроен. Добавьте 'openweather_api_key' в config.yaml"
    
    # Извлекаем название города
    city = _extract_city(text)
    
    # Если город не указан, используем город по умолчанию
    if not city:
        city = config.get("weather", {}).get("default_city", "Москва")
    
    try:
        # Запрос к API OpenWeatherMap
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": api_key,
            "units": "metric",
            "lang": "ru"
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            # Извлекаем данные
            temp = round(data["main"]["temp"])
            feels_like = round(data["main"]["feels_like"])
            description = data["weather"][0]["description"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]
            
            # Формируем ответ
            result = (
                f"🌤️ Погода в городе {city}: {description}. "
                f"Температура {temp}°C, ощущается как {feels_like}°C. "
                f"Влажность {humidity}%, ветер {wind_speed} м/с."
            )
            return result
        
        elif response.status_code == 404:
            return f"⚠️ Город '{city}' не найден."
        else:
            return f"⚠️ Ошибка при получении данных о погоде (код {response.status_code})."
    
    except requests.exceptions.Timeout:
        return "⚠️ Превышено время ожидания ответа от сервера погоды."
    except requests.exceptions.ConnectionError:
        return "⚠️ Нет подключения к интернету. Не могу получить данные о погоде."
    except Exception as e:
        return f"⚠️ Ошибка при получении погоды: {e}"


def _extract_city(text: str) -> str:
    """
    Извлекает название города из текста команды.
    """
    if not text:
        return ""
    
    text = text.lower().strip()
    
    # Убираем служебные слова
    patterns = [
        "какая погода", "погода сейчас", "скажи погоду",
        "что по погоде", "погоду покажи", "погода",
        "how's the weather", "what's the weather", "weather"
    ]
    
    for pattern in patterns:
        text = re.sub(re.escape(pattern.lower()), "", text, flags=re.IGNORECASE)
    
    # Убираем предлоги
    text = re.sub(r"\b(в|на|для|for|in|at)\b", "", text, flags=re.IGNORECASE)
    
    # Очищаем и возвращаем
    city = text.strip()
    
    # Капитализируем первую букву
    if city:
        city = city.capitalize()
    
    return city
