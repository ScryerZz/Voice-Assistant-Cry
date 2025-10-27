"""
Декораторы для навыков ассистента.
Обеспечивают логирование, обработку ошибок, проверку интернета и замеры времени.
"""

import time
import functools
import logging
from .base import check_internet

logger = logging.getLogger("Cry.Decorators")


def log_command(command_name: str):
    """
    Логирует вызов команды.
    
    Args:
        command_name: Название команды для лога
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"📞 Вызов команды: {command_name}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def timeit():
    """
    Измеряет время выполнения функции и логирует результат.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.debug(f"⏱️ {func.__name__} выполнена за {elapsed:.3f}s")
            return result
        return wrapper
    return decorator


def catch_errors(default_return=None):
    """
    Перехватывает исключения и возвращает дефолтное значение или сообщение об ошибке.
    
    Args:
        default_return: Значение, возвращаемое при ошибке (по умолчанию None)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"❌ Ошибка в {func.__name__}: {e}")
                if default_return is not None:
                    return default_return
                return f"⚠️ Ошибка при выполнении команды: {e}"
        return wrapper
    return decorator


def require_internet(offline_message="⚠️ Для этой команды требуется интернет."):
    """
    Проверяет наличие интернета перед выполнением функции.
    
    Args:
        offline_message: Сообщение, возвращаемое при отсутствии интернета
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not check_internet():
                logger.warning(f"🌐 Нет интернета для команды {func.__name__}")
                return offline_message
            return func(*args, **kwargs)
        return wrapper
    return decorator


def retry(max_attempts=3, delay=1.0):
    """
    Повторяет выполнение функции при ошибке.
    
    Args:
        max_attempts: Максимальное количество попыток
        delay: Задержка между попытками (секунды)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"🔄 Попытка {attempt}/{max_attempts} не удалась: {e}")
                    if attempt < max_attempts:
                        time.sleep(delay)
                    else:
                        logger.error(f"❌ Все попытки исчерпаны для {func.__name__}")
                        raise
        return wrapper
    return decorator

