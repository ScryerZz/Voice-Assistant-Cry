import time
import re
import threading
import queue
import logging
import subprocess
import sys

from src.core.console import configure_console_encoding
from src.core.logging_setup import setup_logging
from src.core.recognizer import Recognizer
from src.core.tts import HybridTTS
from src.core.skill_manager import SkillManager
from src.core.executor import Executor
from src.core.config import EXECUTABLE_DIR, IS_FROZEN, PROJECT_ROOT, get_settings
from src.core.reminder_scheduler import ReminderScheduler
from src.core.runtime_control import is_voice_listening_enabled
from src.core.storage import AssistantStorage

configure_console_encoding()
logger = logging.getLogger("Cry")

# === Очереди и глобальные состояния ===
QUEUE_MAXSIZE = 64
WORKERS = []
tts_queue = queue.Queue(maxsize=QUEUE_MAXSIZE)
recognizer_queue = queue.Queue(maxsize=QUEUE_MAXSIZE)


# === Поток TTS ===
def tts_worker(tts: HybridTTS, stop_event: threading.Event | None = None):
    """Обрабатывает очередь озвучки"""
    while not (stop_event and stop_event.is_set()):
        try:
            item = tts_queue.get(timeout=0.2)
        except queue.Empty:
            continue
        if item is None:
            tts_queue.task_done()
            break
        text, lang = item
        try:
            if text:
                tts.speak(text, lang)
        except Exception as e:
            logger.error(f"[TTS ERROR] {e}")
        finally:
            tts_queue.task_done()


def _recognition_result_parts(result, default_lang: str) -> tuple[str, str]:
    if not result:
        return "", default_lang
    if isinstance(result, str):
        return result.strip(), default_lang
    if isinstance(result, (tuple, list)):
        text = str(result[0] or "").strip() if len(result) >= 1 else ""
        lang = str(result[1] or default_lang) if len(result) >= 2 else default_lang
        return text, lang
    return "", default_lang


def recognizer_worker(
    recognizer: Recognizer,
    silence_threshold=3.0,
    stop_event: threading.Event | None = None,
    *,
    output_queue: queue.Queue | None = None,
    prompt_queue: queue.Queue | None = None,
    voice_enabled=None,
    sleep=time.sleep,
):
    """
    Базовая рабочая логика — сразу помещаем распознанные фразы в очередь.
    (Более сложная агрегация по паузе можно вернуть позднее)
    """
    miss_count = 0
    error_count = 0
    output_queue = output_queue or recognizer_queue
    prompt_queue = prompt_queue or tts_queue
    voice_enabled = voice_enabled or is_voice_listening_enabled
    recognition_config = recognizer.config.get("recognition", {}) if hasattr(recognizer, "config") else {}
    miss_threshold = int(recognition_config.get("miss_threshold", 3))
    recover_after_errors = int(recognition_config.get("recover_after_errors", 3))
    repeat_prompt_enabled = bool(recognition_config.get("repeat_prompt_enabled", True))

    while not (stop_event and stop_event.is_set()):
        try:
            if not voice_enabled(default=True):
                sleep(0.25)
                continue
            result = recognizer.listen_text()
            error_count = 0
            text, lang = _recognition_result_parts(result, recognizer.default_lang)
            if text:
                miss_count = 0
                output_queue.put((text, lang))
            else:
                miss_count += 1
                if repeat_prompt_enabled and miss_count >= miss_threshold:
                    prompt_queue.put(("Извини, я не понял, повторите...", recognizer.default_lang))
                    logger.info("🤔 Не понял, повторите...")
                    miss_count = 0
                sleep(0.05)
        except Exception as e:
            error_count += 1
            logger.error(f"[Recognizer ERROR] {e}")
            if error_count >= recover_after_errors and hasattr(recognizer, "recover"):
                logger.warning("Перезапускаю аудиопоток после серии ошибок распознавания.")
                recognizer.recover()
                error_count = 0
            sleep(0.5)


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
                 active_state: dict, storage: AssistantStorage | None = None):
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
            record_command_history(storage, text, cleaned, lang, executor, response)
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
        skills.context["dataset"] = dataset
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
    record_command_history(storage, text, cleaned_text, lang, executor, response)
    if response:
        tts_queue.put((response, lang))
        active_state["last"] = time.time()
    else:
        tts_queue.put(("Не понял, повторите.", lang))


def record_command_history(
    storage: AssistantStorage | None,
    raw_text: str,
    normalized_text: str,
    lang: str,
    executor: Executor,
    response: str | None,
):
    if not storage:
        return
    try:
        trace = executor.last_trace or {}
        storage.add_command_history(
            source="voice",
            raw_text=raw_text,
            normalized_text=normalized_text,
            language=lang,
            status=str(trace.get("status", "unknown")),
            actions=list(trace.get("actions", [])),
            patterns=list(trace.get("patterns", [])),
            scores=list(trace.get("scores", [])),
            response=response,
        )
    except Exception as exc:
        logger.warning(f"[History ERROR] {exc}")


# === Главная функция запуска ===
def main():
    settings = get_settings()
    config = settings.config
    if not config.get("first_run_completed", False):
        print("Первичная настройка не завершена. Открываю окно настроек...")
        command = [sys.executable] if IS_FROZEN else [sys.executable, "ui.py"]
        cwd = EXECUTABLE_DIR if IS_FROZEN else PROJECT_ROOT
        subprocess.run(command, cwd=str(cwd), check=False)
        settings.reload()
        config = settings.config
        if not config.get("first_run_completed", False):
            print("Настройка не завершена. Запуск ассистента отменён.")
            return

    dataset = settings.dataset
    log_file = setup_logging(config)
    logger.info(f"📝 Журнал: {log_file}")

    recognizer = Recognizer(config)
    tts = HybridTTS(config)
    storage = AssistantStorage(config.get("paths", {}).get("database"))
    reminders = ReminderScheduler(storage, tts=tts)
    reminders.start()
    stop_event = threading.Event()

    context = {
        "config": config,
        "dataset": dataset,
        "workers": WORKERS,
        "tts": tts,
        "recognizer": recognizer,
        "storage": storage,
    }
    skills = SkillManager(context=context)
    executor = Executor(dataset, skills, config=config)

    wake_words = build_wake_words(config)
    logger.info(f"🎧 Слова активации: {', '.join(wake_words)}")

    # === Запуск потоков ===
    tts_thread = threading.Thread(target=tts_worker, args=(tts, stop_event), daemon=True, name="tts_worker")
    recognizer_thread = threading.Thread(
        target=recognizer_worker,
        args=(recognizer, 3.0, stop_event),
        daemon=True,
        name="recognizer_worker",
    )
    tts_thread.start()
    recognizer_thread.start()
    WORKERS.extend([tts_thread, recognizer_thread, reminders])

    active_state = {"active": False, "last": 0.0, "timeout": 20.0}
    logger.info("🤖 Cry запущен и слушает...")

    try:
        while not stop_event.is_set():
            try:
                text, lang = recognizer_queue.get(timeout=0.1)
                if text:
                    process_text(executor, dataset, skills, text, lang, wake_words, active_state, storage)
            except queue.Empty:
                continue
            except KeyboardInterrupt:
                logger.info("🛑 Завершение работы по Ctrl+C")
                break
            except Exception as e:
                logger.error(f"[MAIN ERROR] {e}")
                time.sleep(0.3)
    finally:
        stop_event.set()
        tts_queue.put(None)
        try:
            reminders.stop()
            reminders.join(timeout=2.0)
        except Exception as exc:
            logger.warning(f"[Reminder shutdown ERROR] {exc}")
        try:
            recognizer.stop()
        except Exception as exc:
            logger.warning(f"[Recognizer shutdown ERROR] {exc}")
        for worker in (tts_thread, recognizer_thread):
            worker.join(timeout=2.0)


if __name__ == "__main__":
    main()
