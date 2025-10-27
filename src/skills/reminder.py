import time
import re
import threading
from datetime import datetime, timedelta


def set_timer(*args, **kwargs):
    """
    Устанавливает таймер на указанное количество секунд/минут.
    Примеры: "поставь таймер на 5 минут", "таймер на 30 секунд"
    """
    text = kwargs.get("text", "") or " ".join(str(a) for a in args if isinstance(a, str))
    text = text.strip().lower()
    tts = kwargs.get("tts")
    
    if not text:
        return "⚠️ Не понял, на сколько установить таймер."
    
    # Извлекаем время
    seconds = 0
    
    # Поиск минут
    min_match = re.search(r"(\d+)\s*(минут|минуты|минуту|minute|minutes)", text)
    if min_match:
        seconds += int(min_match.group(1)) * 60
    
    # Поиск секунд
    sec_match = re.search(r"(\d+)\s*(секунд|секунды|секунду|second|seconds)", text)
    if sec_match:
        seconds += int(sec_match.group(1))
    
    # Если не нашли конкретное время, пробуем просто число
    if seconds == 0:
        num_match = re.search(r"(\d+)", text)
        if num_match:
            seconds = int(num_match.group(1)) * 60  # по умолчанию минуты
    
    if seconds == 0:
        return "⚠️ Не понял, на сколько времени установить таймер."
    
    def timer_thread():
        time.sleep(seconds)
        if tts:
            try:
                tts.speak("⏰ Таймер завершён!", lang="ru")
            except Exception:
                print("⏰ Таймер завершён!")
        else:
            print("⏰ Таймер завершён!")
    
    threading.Thread(target=timer_thread, daemon=True).start()
    
    if seconds >= 60:
        minutes = seconds // 60
        return f"⏰ Таймер установлен на {minutes} минут."
    return f"⏰ Таймер установлен на {seconds} секунд."


def set_reminder(*args, **kwargs):
    """
    Устанавливает напоминание с текстом и задержкой.
    Примеры: "напомни через 5 минут купить молоко", "напомни через час позвонить"
    """
    text = kwargs.get("text", "") or " ".join(str(a) for a in args if isinstance(a, str))
    text = text.strip().lower()
    tts = kwargs.get("tts")
    
    if not text:
        return "⚠️ Не понял, о чём напомнить."
    
    # Убираем служебные слова
    clean_text = re.sub(r"\b(напомни|напоминание|remind|reminder)\b", "", text, flags=re.IGNORECASE)
    
    # Извлекаем время задержки
    delay_seconds = 0
    
    # Поиск часов
    hour_match = re.search(r"через\s+(\d+)\s*(час|часа|часов|hour|hours)", clean_text)
    if hour_match:
        delay_seconds += int(hour_match.group(1)) * 3600
        clean_text = re.sub(r"через\s+\d+\s*(час|часа|часов|hour|hours)", "", clean_text)
    
    # Поиск минут
    min_match = re.search(r"через\s+(\d+)\s*(минут|минуты|минуту|minute|minutes)", clean_text)
    if min_match:
        delay_seconds += int(min_match.group(1)) * 60
        clean_text = re.sub(r"через\s+\d+\s*(минут|минуты|минуту|minute|minutes)", "", clean_text)
    
    # Если время не указано, ставим 5 минут по умолчанию
    if delay_seconds == 0:
        delay_seconds = 300
    
    # Очищаем текст напоминания
    clean_text = clean_text.strip()
    if not clean_text:
        clean_text = "время вышло"
    
    def reminder_thread():
        time.sleep(delay_seconds)
        reminder_text = f"🔔 Напоминание: {clean_text}"
        if tts:
            try:
                tts.speak(reminder_text, lang="ru")
            except Exception:
                print(reminder_text)
        else:
            print(reminder_text)
    
    threading.Thread(target=reminder_thread, daemon=True).start()
    
    if delay_seconds >= 3600:
        hours = delay_seconds // 3600
        return f"🔔 Напоминание установлено на {hours} час(а): {clean_text}"
    elif delay_seconds >= 60:
        minutes = delay_seconds // 60
        return f"🔔 Напоминание установлено на {minutes} минут: {clean_text}"
    return f"🔔 Напоминание установлено на {delay_seconds} секунд: {clean_text}"
