import os
import requests
from typing import Optional


class AISkill:
    """
    Навык общения с ИИ через ЯндексGPT.
    ЯндексGPT - российская языковая модель от Яндекса.
    Работает через API Yandex Cloud Foundation Models.
    """

    def __init__(self, api_key: Optional[str] = None, folder_id: Optional[str] = None, 
                 enabled: bool = True, debug: bool = False):
        self.api_key = api_key or os.getenv("YANDEXGPT_API_KEY")
        self.folder_id = folder_id or os.getenv("YANDEX_FOLDER_ID")
        self.enabled = enabled and bool(self.api_key) and bool(self.folder_id)
        self.debug = debug
        # Эндпоинт API ЯндексGPT.
        self.endpoint = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        # Модели: yandexgpt-lite (быстрая, бесплатная), yandexgpt (стандартная)
        self.model = f"gpt://{self.folder_id}/yandexgpt-lite/latest"

    def ask(self, prompt: str, lang: str = "ru") -> str:
        """
        Отправляет текст в ЯндексGPT и возвращает ответ.
        Использует API Yandex Cloud Foundation Models.
        """
        if not self.enabled:
            if self.debug:
                print("[AISkill] AI module disabled")
            return "🤖 ИИ-модуль сейчас не активен."

        if not self.api_key:
            if self.debug:
                print("[AISkill] API key missing")
            return "⚠️ Не найден API-ключ ЯндексGPT. Добавьте его в настройках."

        if not self.folder_id:
            if self.debug:
                print("[AISkill] Folder ID missing")
            return "⚠️ Не найден ID каталога Яндекс Облака. Укажите его в настройках."

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
        
        # ЯндексGPT использует свой формат запроса.
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
                # ЯндексGPT возвращает ответ в поле result.alternatives[0].message.text.
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
                return "⚠️ Неверный API-ключ ЯндексGPT. Проверьте настройки."
            elif response.status_code == 403:
                return "⚠️ Доступ запрещён. Проверьте ID каталога и права доступа."
            elif response.status_code == 400:
                return self._bad_request_message(response)
            elif response.status_code == 429:
                return "⚠️ Превышен лимит запросов ЯндексGPT. Попробуйте позже."
            else:
                return "⚠️ Ошибка при обращении к ЯндексGPT. Попробуйте позже."

        except requests.exceptions.Timeout:
            if self.debug:
                print("[AISkill] TIMEOUT")
            return "⚠️ ИИ не ответил вовремя."
        
        except requests.exceptions.ConnectionError:
            if self.debug:
                print("[AISkill] NO CONNECTION")
            return "⚠️ Нет подключения к сети. Работаю офлайн."
        
        except Exception as e:
            if self.debug:
                print(f"[AISkill] ERROR: {e}")
            return "⚠️ Произошла непредвиденная ошибка при обращении к ИИ."

    def _bad_request_message(self, response) -> str:
        try:
            message = str((response.json().get("error") or {}).get("message") or "")
        except Exception:
            message = str(getattr(response, "text", "") or "")

        normalized = message.lower()
        if "folder id" in normalized and "does not match" in normalized:
            return (
                "⚠️ ID каталога Яндекс Облака не совпадает с каталогом сервисного аккаунта. "
                "Проверьте поле «ID каталога Яндекс Облака» в настройках."
            )
        if "model" in normalized or "modeluri" in normalized:
            return "⚠️ ЯндексGPT отклонил модель запроса. Проверьте ID каталога и доступность модели."
        return "⚠️ ЯндексGPT отклонил запрос. Проверьте ID каталога и параметры интеграции."
