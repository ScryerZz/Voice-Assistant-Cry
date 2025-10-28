"""
Навык управления приложениями.
Открытие и закрытие популярных программ.
"""
import os
import platform
import subprocess
from pathlib import Path


# === Словарь приложений ===
# Структура: имя_приложения: {path: путь, process: имя процесса}
APPS = {
    "telegram": {
        "path": "C:/Users/coderzxc/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Telegram Desktop/Telegram.lnk",
        "process": "Telegram.exe"
    },
    "yamusic": {
        "path": "C:/Users/coderzxc/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Яндекс Музыка.lnk",
        "process": "Яндекс Музыка.exe"
    },
    "discord": {
        "path": "C:/Users/coderzxc/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Discord Inc/Discord.lnk",
        "process": "Discord.exe"
    },
    "steam": {
        "path": "C:/Program Files (x86)/Steam/steam.exe",
        "process": "steam.exe"
    },
    "flstudio": {
        "path": "C:/Program Files/Image-Line/FL Studio 2024/FL64.exe",
        "process": "FL64.exe"
    },
    "msword": {
        "path": "C:/Program Files (x86)/Microsoft Office/root/Office16/WINWORD.EXE",
        "process": "WINWORD.EXE"
    },
    "msexcel": {
        "path": "C:/Program Files (x86)/Microsoft Office/root/Office16/EXCEL.EXE",
        "process": "EXCEL.EXE"
    },
    "mspowerpoint": {
        "path": "C:/Program Files (x86)/Microsoft Office/root/Office16/POWERPNT.EXE",
        "process": "POWERPNT.EXE"
    }
}


def _open_app(app_name: str) -> str:
    """Универсальная функция открытия приложения"""
    if app_name not in APPS:
        return f"Приложение '{app_name}' не найдено."
    
    app_info = APPS[app_name]
    path = app_info["path"]
    
    # Проверка существования файла
    if not Path(path).exists():
        return f"Файл не найден: {path}. Обновите путь в src/skills/apps.py"
    
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        else:
            subprocess.Popen([path])
        return f"{app_name.capitalize()} открыт."
    except Exception as e:
        return f"Ошибка при открытии {app_name}: {str(e)}"


def _close_app(app_name: str) -> str:
    """Универсальная функция закрытия приложения"""
    if app_name not in APPS:
        return f"Приложение '{app_name}' не найдено."
    
    process_name = APPS[app_name]["process"]
    
    try:
        if platform.system() == "Windows":
            result = os.system(f"taskkill /f /im \"{process_name}\" 2>nul")
            if result == 0:
                return f"{app_name.capitalize()} закрыт."
            else:
                return f"{app_name.capitalize()} не запущен или уже закрыт."
        else:
            # Для Linux/macOS
            os.system(f"pkill -9 {process_name.split('.')[0]}")
            return f"{app_name.capitalize()} закрыт."
    except Exception as e:
        return f"Ошибка при закрытии {app_name}: {str(e)}"


# === Telegram ===
def open_telegram(*args, **kwargs):
    """Открыть Telegram"""
    return _open_app("telegram")

def close_telegram(*args, **kwargs):
    """Закрыть Telegram"""
    return _close_app("telegram")


# === Яндекс Музыка ===
def open_yamusic(*args, **kwargs):
    """Открыть Яндекс Музыку"""
    return _open_app("yamusic")

def close_yamusic(*args, **kwargs):
    """Закрыть Яндекс Музыку"""
    return _close_app("yamusic")


# === Discord ===
def open_discord(*args, **kwargs):
    """Открыть Discord"""
    return _open_app("discord")

def close_discord(*args, **kwargs):
    """Закрыть Discord"""
    return _close_app("discord")


# === Steam ===
def open_steam(*args, **kwargs):
    """Открыть Steam"""
    return _open_app("steam")

def close_steam(*args, **kwargs):
    """Закрыть Steam"""
    return _close_app("steam")


# === FL Studio ===
def open_flstudio(*args, **kwargs):
    """Открыть FL Studio"""
    return _open_app("flstudio")

def close_flstudio(*args, **kwargs):
    """Закрыть FL Studio"""
    return _close_app("flstudio")


# === MS Word ===
def open_msword(*args, **kwargs):
    """Открыть Microsoft Word"""
    return _open_app("msword")

def close_msword(*args, **kwargs):
    """Закрыть Microsoft Word"""
    return _close_app("msword")


# === MS Excel ===
def open_msexcel(*args, **kwargs):
    """Открыть Microsoft Excel"""
    return _open_app("msexcel")

def close_msexcel(*args, **kwargs):
    """Закрыть Microsoft Excel"""
    return _close_app("msexcel")


# === MS PowerPoint ===
def open_mspowerpoint(*args, **kwargs):
    """Открыть Microsoft PowerPoint"""
    return _open_app("mspowerpoint")

def close_mspowerpoint(*args, **kwargs):
    """Закрыть Microsoft PowerPoint"""
    return _close_app("mspowerpoint")