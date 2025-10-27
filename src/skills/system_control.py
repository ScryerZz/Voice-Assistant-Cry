"""
Модуль управления системой: скриншоты, громкость, очистка.
Объединяет функции из default/windows/
"""

import os
import shutil
import ctypes
import platform
import tempfile
from datetime import datetime
from pathlib import Path

# Опциональные импорты
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    if platform.system() == "Windows":
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        PYCAW_AVAILABLE = True
    else:
        PYCAW_AVAILABLE = False
except ImportError:
    PYCAW_AVAILABLE = False


# ============================================================
# СКРИНШОТЫ
# ============================================================

def screenshot(*args, **kwargs):
    """Делает скриншот экрана и сохраняет на рабочий стол"""
    
    if not PYAUTOGUI_AVAILABLE:
        return "⚠️ Модуль pyautogui не установлен. Установите: pip install pyautogui"
    
    try:
        # Определяем путь к рабочему столу
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            desktop = Path.home() / "Рабочий стол"  # для русской Windows
        if not desktop.exists():
            desktop = Path.home()  # используем домашнюю папку
        
        # Генерируем имя файла
        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = desktop / filename
        
        # Делаем скриншот
        image = pyautogui.screenshot()
        image.save(str(filepath))
        
        return f"📸 Скриншот сохранён: {filepath.name}"
    
    except Exception as e:
        return f"❌ Ошибка при создании скриншота: {e}"


# ============================================================
# УПРАВЛЕНИЕ ГРОМКОСТЬЮ
# ============================================================

def _control_volume(volume: float) -> bool:
    """Внутренняя функция для управления громкостью"""
    if not PYCAW_AVAILABLE:
        return False
    
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume_control = interface.QueryInterface(IAudioEndpointVolume)
        volume_control.SetMasterVolumeLevelScalar(volume, None)
        return True
    except Exception:
        return False


def set_volume_max(*args, **kwargs):
    """Устанавливает максимальную громкость (100%)"""
    if _control_volume(1.0):
        return "🔊 Громкость установлена на максимум (100%)."
    return "⚠️ Управление громкостью недоступно на этой системе."


def set_volume_high(*args, **kwargs):
    """Устанавливает высокую громкость (75%)"""
    if _control_volume(0.75):
        return "🔊 Громкость установлена на 75%."
    return "⚠️ Управление громкостью недоступно на этой системе."


def set_volume_mid(*args, **kwargs):
    """Устанавливает среднюю громкость (50%)"""
    if _control_volume(0.5):
        return "🔊 Громкость установлена на 50%."
    return "⚠️ Управление громкостью недоступно на этой системе."


def set_volume_low(*args, **kwargs):
    """Устанавливает низкую громкость (25%)"""
    if _control_volume(0.25):
        return "🔉 Громкость установлена на 25%."
    return "⚠️ Управление громкостью недоступно на этой системе."


def set_volume_min(*args, **kwargs):
    """Выключает звук (0%)"""
    if _control_volume(0.0):
        return "🔇 Звук выключен."
    return "⚠️ Управление громкостью недоступно на этой системе."


# ============================================================
# ОЧИСТКА СИСТЕМЫ
# ============================================================

def clear_temp(*args, **kwargs):
    """Очищает временную папку"""
    
    temp_path = Path(tempfile.gettempdir())
    deleted_count = 0
    failed_count = 0
    
    try:
        for item in temp_path.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                    deleted_count += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    deleted_count += 1
            except Exception:
                failed_count += 1
        
        return f"🗑️ Временные файлы: удалено {deleted_count}, пропущено {failed_count}."
    
    except Exception as e:
        return f"❌ Ошибка при очистке временных файлов: {e}"


def clear_recycle_bin(*args, **kwargs):
    """Очищает корзину (только Windows)"""
    
    if platform.system() != "Windows":
        return "⚠️ Очистка корзины доступна только на Windows."
    
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x0007)
        return "✅ Корзина очищена."
    except Exception as e:
        return f"❌ Не удалось очистить корзину: {e}"


def clear_downloads(*args, **kwargs):  # pyright: ignore[reportUnusedParameter, reportUnusedParameter]
    # """Очищает папку загрузок, сохраняя важные файлы"""
    
    # keep_extensions = [
    #     ".img", ".iso",
    #     ".jpeg", ".jpg", ".png", ".gif", ".webp",
    #     ".mp3", ".wav", ".flac",
    #     ".mp4", ".mkv", ".avi",
    #     ".pdf", ".docx", ".xlsx", ".zip", ".rar"
    # ]
    
    # downloads_path = Path.home() / "Downloads"
    # if not downloads_path.exists():
    #     downloads_path = Path.home() / "Загрузки"  # для русской Windows
    
    # if not downloads_path.exists():
    #     return "⚠️ Папка загрузок не найдена."
    
    # deleted_count = 0
    # failed_count = 0
    
    # try:
    #     for item in downloads_path.iterdir():
    #         try:
    #             if item.is_file() and item.suffix.lower() not in keep_extensions:
    #                 item.unlink()
    #                 deleted_count += 1
    #             elif item.is_dir():
    #                 shutil.rmtree(item)
    #                 deleted_count += 1
    #         except Exception:
    #             failed_count += 1
        
    #     return f"🗑️ Загрузки: удалено {deleted_count}, пропущено {failed_count}."
    
    # except Exception as e:
    #     return f"❌ Ошибка при очистке загрузок: {e}"
    return "❌ Фунция очистки этого раздела закомментирована и не выполняется!"


def clean_system(*args, **kwargs):
    # """Выполняет полную очистку: корзина, загрузки, temp"""
    # results = []
    
    # results.append(clear_recycle_bin())
    # results.append(clear_downloads())
    # results.append(clear_temp())
    
    # return "✅ Очистка завершена.\n" + "\n".join(results)
    return "❌ Фунция очистки этого раздела закомментирована и не выполняется!"

