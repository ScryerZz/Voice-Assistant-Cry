import os
import requests
from typing import Optional


class AISkill:
    """
    Навык общения с AI (YandexGPT API)
    YandexGPT - российская языковая модель от Яндекса.
    Работает через Yandex Cloud Foundation Models API.
    """

    def __init__(self, api_key: Optional[str] = None, folder_id: Optional[str] = None, 
                 enabled: bool = True, debug: bool = False):
        self.api_key = api_key or os.getenv("YANDEXGPT_API_KEY")
        self.folder_id = folder_id or os.getenv("YANDEX_FOLDER_ID")
        self.enabled = enabled and bool(self.api_key) and bool(self.folder_id)
        self.debug = debug
        # YandexGPT API endpoint
        self.endpoint = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        # Модели: yandexgpt-lite (быстрая, бесплатная), yandexgpt (стандартная)
        self.model = f"gpt://{self.folder_id}/yandexgpt-lite/latest"

    def ask(self, prompt: str, lang: str = "ru") -> str:
        """
        Отправляет текст в YandexGPT и возвращает ответ.
        Использует Yandex Cloud Foundation Models API.
        """
        if not self.enabled:
            if self.debug:
                print("[AISkill] AI module disabled")
            return "🤖 AI-модуль сейчас не активен."

        if not self.api_key:
            if self.debug:
                print("[AISkill] API key missing")
            return "⚠️ Не найден ключ YandexGPT API. Получите на cloud.yandex.ru"

        if not self.folder_id:
            if self.debug:
                print("[AISkill] Folder ID missing")
            return "⚠️ Не найден Folder ID. Укажите его в настройках."

        # Системный промпт в зависимости от языка
        system_prompts = {
            "ru": "Ты — дружелюбный голосовой ассистент по имени Cry. Отвечай кратко и по делу, максимум 2-3 предложения.",
            "en": "You are a friendly voice assistant named Cry. Answer briefly and to the point, maximum 2-3 sentences."
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {self.api_key}",
            "x-folder-id": self.folder_id
        }
        
        # YandexGPT использует свой формат запроса
        data = {
            "modelUri": self.model,
            "completionOptions": {
                "stream": False,
                "temperature": 0.6,
                "maxTokens": 500
            },
            "messages": [
                {
                    "role": "system",
                    "text": system_prompts.get(lang, system_prompts["ru"])
                },
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=data,
                timeout=20
            )

            if response.status_code == 200:
                result = response.json()
                # YandexGPT возвращает ответ в поле result.alternatives[0].message.text
                alternatives = result.get("result", {}).get("alternatives", [])
                if alternatives:
                    text = alternatives[0].get("message", {}).get("text", "").strip()
                else:
                    text = ""
                
                if not text:
                    text = "🤖 Извини, я не смог придумать ответ."
                
                if self.debug:
                    print(f"[AISkill] OK Response: {text[:100]}")
                
                return text

            # Обработка API-ошибок
            if self.debug:
                error_msg = response.text[:200]
                print(f"[AISkill] ERROR API {response.status_code}: {error_msg}")
            
            # Специфичные ошибки
            if response.status_code == 401:
                return "⚠️ Неверный API ключ YandexGPT. Проверьте настройки."
            elif response.status_code == 403:
                return "⚠️ Доступ запрещен. Проверьте Folder ID и права доступа."
            elif response.status_code == 429:
                return "⚠️ Превышен лимит запросов YandexGPT. Попробуйте позже."
            else:
                return "⚠️ Ошибка при обращении к YandexGPT. Попробуйте позже."

        except requests.exceptions.Timeout:
            if self.debug:
                print("[AISkill] TIMEOUT")
            return "⚠️ AI не ответил вовремя."
        
        except requests.exceptions.ConnectionError:
            if self.debug:
                print("[AISkill] NO CONNECTION")
            return "⚠️ Нет подключения к сети. Работаю офлайн."
        
        except Exception as e:
            if self.debug:
                print(f"[AISkill] ERROR: {e}")
            return "⚠️ Произошла непредвиденная ошибка при обращении к AI."

