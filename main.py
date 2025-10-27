import time
import re
import threading
import queue
import logging

from src.core.recognizer import Recognizer
from src.core.tts import HybridTTS
from src.core.skill_manager import SkillManager
from src.core.executor import Executor
from src.core.config import get_settings

# === Настройка логирования ===
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Cry")

# === Очереди и глобальные состояния ===
WORKERS = []
tts_queue = queue.Queue()
recognizer_queue = queue.Queue()


# === Поток TTS ===
def tts_worker(tts: HybridTTS):
    """Обрабатывает очередь озвучки"""
    while True:
        text, lang = tts_queue.get()
        try:
            if text:
                tts.speak(text, lang)
        except Exception as e:
            logger.error(f"[TTS ERROR] {e}")
        finally:
            tts_queue.task_done()

def recognizer_worker(recognizer: Recognizer, silence_threshold=3.0):
    """
    Базовая рабочая логика — сразу помещаем распознанные фразы в очередь.
    (Более сложная агрегация по паузе можно вернуть позднее)
    """
    miss_count = 0
    miss_threshold = 3

    while True:
        try:
            result = recognizer.listen_text()
            if result:
                miss_count = 0
                text, lang = result
                if text:
                    recognizer_queue.put((text.strip(), lang))
            else:
                miss_count += 1
                if miss_count >= miss_threshold:
                    tts_queue.put(("Извини, я не понял, повторите...", recognizer.default_lang))
                    logger.info("🤔 Не понял, повторите...")
                    miss_count = 0
                time.sleep(0.05)
        except Exception as e:
            logger.error(f"[Recognizer ERROR] {e}")
            time.sleep(0.5)
# === Поток прослушивания ===
# def recognizer_worker(recognizer: Recognizer, silence_threshold=3.0):
#     """Постоянно слушает микрофон и отправляет фразы в очередь"""
#     last_speech_time = 0
#     buffer_text = ""

#     while True:
#         try:
#             result = recognizer.listen_text()
#             if result:
#                 text, lang = result
#                 buffer_text = text
#                 last_speech_time = time.time()
#                 recognizer_queue.put((buffer_text.strip(), lang))
#             else:
#                 # Проверяем тишину
#                 if buffer_text and time.time() - last_speech_time >= silence_threshold:
#                     recognizer_queue.put((buffer_text.strip(), None))
#                     buffer_text = ""
#                 time.sleep(0.15)
#         except Exception as e:
#             logger.error(f"[Recognizer ERROR] {e}")
#             time.sleep(0.5)
#             recognizer.stop()


# === Вспомогательные функции ===
def clean_text(text: str, wake_word: str = None) -> str:
    """Удаляет wake word из текста"""
    if not text:
        return ""
    if wake_word:
        text = re.sub(rf"\b{re.escape(wake_word)}\b", "", text, flags=re.IGNORECASE)
    return text.strip().lower()


def is_reload_command(text: str, meta: dict, key: str) -> bool:
    """Проверяет, является ли команда командой перезагрузки"""
    if not text or not meta:
        return False
    patterns = meta.get(key, {}).get("patterns", [])
    return any(text == p.lower() for p in patterns)


def build_wake_words(config: dict) -> set:
    """Извлекает все слова активации из конфигурации"""
    wake_words = set()

    for lang, words in (config.get("wake_words") or {}).items():
        if isinstance(words, list):
            wake_words.update(map(str.lower, words))

    # добавляем старое поле для совместимости
    single_word = config.get("wake_word")
    if single_word:
        wake_words.add(single_word.lower())

    return wake_words


# === Основная логика ассистента ===
def process_text(executor: Executor, dataset: dict, skills: SkillManager,
                 text: str, lang: str, wake_words: set,
                 active_state: dict):
    """Главная функция обработки текста"""

    normalized = text.lower().strip()
    lang = lang or "ru"
    logger.info(f"🧠 Распознано ({lang}): {normalized}")

    # === Обработка Wake Word ===
    if not active_state["active"]:
        triggered = next((w for w in wake_words if re.search(rf"\b{re.escape(w)}\b", normalized)), None)

        if triggered:
            cleaned = clean_text(normalized, triggered)
            active_state["active"] = True
            active_state["last"] = time.time()

            if not cleaned:
                logger.info(f"🚀 Активирован wake word: '{triggered}'")
                tts_queue.put(("Слушаю вас.", lang))
                return

            logger.info(f"🚀 Wake word '{triggered}', сразу выполняю команду: {cleaned}")
            response = executor.handle(cleaned, lang=lang)
            if response:
                tts_queue.put((response, lang))
            return
        return  # не активирован — ждём wake word

    # === Проверка тайм-аута активности ===
    if time.time() - active_state["last"] > active_state["timeout"]:
        logger.info("😴 Время активности истекло.")
        active_state["active"] = False
        return

    # === Обработка команд ===
    triggered = next((w for w in wake_words if w in normalized), None)
    cleaned_text = clean_text(normalized, triggered)
    if not cleaned_text:
        tts_queue.put(("Да, я слушаю.", lang))
        return

    meta = dataset.get("meta", {}) or {}

    # === Системные команды ===
    if is_reload_command(cleaned_text, meta, "reload_dataset"):
        logger.info("🔁 Перезагрузка датасета...")
        new_settings = get_settings()
        dataset = new_settings.dataset
        executor.update_dataset(dataset)
        skills.reload()
        msg = meta.get("reload_dataset", {}).get("response", {}).get(lang, "Данные обновлены.")
        tts_queue.put((msg, lang))
        return

    if is_reload_command(cleaned_text, meta, "restart_skills"):
        logger.info("🔁 Перезапуск навыков...")
        skills.reload()
        msg = meta.get("restart_skills", {}).get("response", {}).get(lang, "Навыки перезапущены.")
        tts_queue.put((msg, lang))
        return

    # === Выполнение команды пользователя ===
    response = executor.handle(cleaned_text, lang=lang)
    if response:
        tts_queue.put((response, lang))
        active_state["last"] = time.time()
    else:
        tts_queue.put(("Не понял, повторите.", lang))


# === Главная функция запуска ===
def main():
    settings = get_settings()
    config = settings.config
    dataset = settings.dataset

    recognizer = Recognizer(config)
    tts = HybridTTS(config)

    context = {"config": config, "dataset": dataset, "workers": WORKERS, "tts": tts}
    skills = SkillManager(context=context)
    executor = Executor(dataset, skills, config=config)

    wake_words = build_wake_words(config)
    logger.info(f"🎧 Слова активации: {', '.join(wake_words)}")

    # === Запуск потоков ===
    threading.Thread(target=tts_worker, args=(tts,), daemon=True).start()
    threading.Thread(target=recognizer_worker, args=(recognizer,), daemon=True).start()

    active_state = {"active": False, "last": 0.0, "timeout": 20.0}
    logger.info("🤖 Cry запущен и слушает...")

    while True:
        try:
            text, lang = recognizer_queue.get(timeout=0.1)
            if text:
                process_text(executor, dataset, skills, text, lang, wake_words, active_state)
        except queue.Empty:
            continue
        except KeyboardInterrupt:
            logger.info("🛑 Завершение работы по Ctrl+C")
            break
        except Exception as e:
            logger.error(f"[MAIN ERROR] {e}")
            time.sleep(0.3)


if __name__ == "__main__":
    main()

# import time
# import re
# import threading
# import queue
# import logging


# from src.core.recognizer import Recognizer
# from src.core.tts import HybridTTS
# from src.core.skill_manager import SkillManager
# from src.core.executor import Executor
# from src.core.config import get_settings

# # === Логирование ===
# logging.basicConfig(
#     level=logging.INFO,
#     format="[%(asctime)s] [%(levelname)s] %(message)s",
#     datefmt="%H:%M:%S"
# )
# logger = logging.getLogger("Assistant")

# WORKERS = []
# tts_queue = queue.Queue()
# recognizer_queue = queue.Queue()


# # === Поток TTS ===
# def tts_worker(tts: HybridTTS):
#     while True:
#         text, lang = tts_queue.get()
#         if not text:
#             continue
#         try:
#             if text:
#                 tts.speak(text, lang)
#         except Exception as e:
#             logger.error(f"[TTS ERROR] {e}")
#         finally:
#             tts_queue.task_done()


# # === Поток прослушивания ===
# def recognizer_worker(recognizer: Recognizer, silence_threshold=3.0):
#     """
#     Постоянно слушает микрофон.
#     Если пользователь делает паузу > silence_threshold секунд — считаем, что он закончил говорить.
#     """
#     last_speech_time = 0
#     buffer_text = ""

#     while True:
#         try:
#             result = recognizer.listen_text()
#             if result:
#                 text, lang = result
#                 buffer_text = text
#                 last_speech_time = time.time()

#                 # Если пользователь всё ещё говорит — ждём окончания
#                 recognizer_queue.put((buffer_text.strip(), lang))

#             else:
#                 # Проверяем, не истекла ли пауза
#                 if time.time() - last_speech_time >= silence_threshold and buffer_text:
#                     # Отправляем накопленный текст на обработку
#                     recognizer_queue.put((buffer_text.strip(), None))
#                     buffer_text = ""

#                 time.sleep(0.2)

#         except Exception as e:
#             logger.error(f"[Recognizer ERROR] {e}")
#             time.sleep(0.5)
#             recognizer.stop()


# # === Удаляем wake word из текста ===
# def clean_text(text: str, wake_word: str) -> str:
#     if not text:
#         return ""
#     pattern = r"(^|\b)" + re.escape(wake_word) + r"(\b|$)"
#     return re.sub(pattern, "", text.lower(), flags=re.IGNORECASE).strip()


# # === Проверяем команды перезагрузки ===
# def is_reload_command(text: str, meta: dict, key: str) -> bool:
#     if not text or not meta:
#         return False
#     patterns = meta.get(key, {}).get("patterns", [])
#     return any(text == p.lower() for p in patterns)


# # === Основная функция ===
# def main():
#     settings = get_settings()
#     config = settings.config
#     dataset = settings.dataset

#     recognizer = Recognizer(config)
#     tts = HybridTTS(config)
#     context = {
#         "config": config,
#         "dataset": dataset,
#         "workers": WORKERS,
#         "tts": tts
#     }
#     skills = SkillManager(context=context)
#     executor = Executor(dataset, skills, config=config)

#     # === Настройка wake words ===
#     wake_words_config = config.get("wake_words", {})
#     wake_words = set()

#     if isinstance(wake_words_config, dict):
#         for lang, words in wake_words_config.items():
#             if isinstance(words, list):
#                 wake_words.update(w.lower().strip() for w in words)

#     # добавляем старый wake_word для совместимости
#     single_word = config.get("wake_word", "")
#     if single_word:
#         wake_words.add(single_word.lower().strip())

#     logger.info(f"🎧 Слова активации: {', '.join(wake_words)}")

#     # === Состояния ===
#     active_mode = False
#     last_activation = 0
#     active_duration = 20  # больше времени, чтобы не спешить

#     thread1 = threading.Thread(target=tts_worker, args=(tts,), daemon=True)
#     thread2 = threading.Thread(target=recognizer_worker, args=(recognizer,), daemon=True)
#     thread1.start()
#     thread2.start()
    
#     WORKERS.extend([thread1, thread2])

#     logger.info("🤖 Cry запущен и слушает...")

#     while True:
#         try:
#             try:
#                 result = recognizer_queue.get(timeout=0.1)
#             except queue.Empty:
#                 time.sleep(0.1)
#                 continue

#             if not result:
#                 continue

#             text, lang = result
#             if not text:
#                 continue
            
#             normalized = text.lower().strip()
            
#             lang = lang or "ru"
#             logger.info(f"🧠 Распознано ({lang}): {normalized}")

#             # === Проверяем wake word ===
#             if not active_mode:
#                 triggered = next((w for w in wake_words if w in normalized), None)

#                 if triggered:
#                     cleaned = clean_text(normalized, triggered).strip()

#                     if not cleaned or cleaned in ("", triggered):
#                         active_mode = True
#                         last_activation = time.time()
#                         logger.info(f"🚀 Активирован wake word: '{triggered}'")
#                         tts_queue.put(("Слушаю вас.", lang))

#                     active_mode = True
#                     last_activation = time.time()
#                     logger.info(f"🚀 Активирован wake word: '{triggered}'")
#                     response = executor.handle(cleaned, lang=lang)
#                     if response:
#                         logger.info(f"🤖 Cry: {response}")
#                         tts_queue.put((response, lang))

#                 else:
#                     continue

#             # === Проверка тайм-аута активности ===
#             if time.time() - last_activation > active_duration:
#                 logger.info("😴 Время активности истекло. Ожидание нового вызова.")
#                 active_mode = False
#                 continue

#             # === Обработка команды ===
#             triggered_word = next((w for w in wake_words if w in normalized), None)
#             cleaned_text = clean_text(normalized, triggered_word) if triggered_word else normalized
#             meta = dataset.get("meta", {}) or {}

#             if not cleaned_text:
#                 tts_queue.put(("Да, я слушаю.", lang))
#                 continue

#             # === Проверяем специальные команды ===
#             if is_reload_command(cleaned_text, meta, "reload_dataset"):
#                 settings = get_settings()
#                 dataset = settings.dataset
#                 executor.update_dataset(dataset)
#                 skills.reload()
#                 msg = meta.get("reload_dataset", {}).get("response", {}).get(lang, "Данные обновлены.")
#                 logger.info(msg)
#                 tts_queue.put((msg, lang))
#                 continue

#             if is_reload_command(cleaned_text, meta, "restart_skills"):
#                 skills.reload()
#                 msg = meta.get("restart_skills", {}).get("response", {}).get(lang, "Навыки перезапущены.")
#                 logger.info(msg)
#                 tts_queue.put((msg, lang))
#                 continue

#             # === Выполнение обычных команд ===
#             response = executor.handle(cleaned_text, lang=lang)
#             if response:
#                 logger.info(f"🤖 Cry: {response}")
#                 tts_queue.put((response, lang))
#                 last_activation = time.time()
#                 active_duration = 20
#                 print(f"⏱️ Активное время продлено на 20 сек (итого {active_duration})")
#             else:
#                 tts_queue.put(("Не понял, повторите.", lang))

#         except KeyboardInterrupt:
#             logger.info("\n🛑 Завершение работы...")
#             break
        
#         except Exception as e:
#             logger.error(f"[MAIN ERROR] {e}")
#             time.sleep(0.3)
#             continue


# if __name__ == "__main__":
#     main()
