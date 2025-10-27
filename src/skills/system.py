import os
import webbrowser
import platform

def open_browser(*args, **kwargs):
    try:
        # cross-platform try
        webbrowser.open("https://www.google.com")
        return "Открываю браузер."
    except Exception as e:
        return f"Ошибка при открытии браузера: {e}"


def shutdown(*args, **kwargs):
    # """Выключает компьютер (кросс-платформенно)"""
    # try:
    #     if platform.system() == "Windows":
    #         os.system("shutdown /s /t 1")
    #         return "💤 Выключаю компьютер через 1 секунду."
    #     elif platform.system() == "Linux":
    #         os.system("systemctl poweroff")
    #         return "💤 Выключаю компьютер."
    #     elif platform.system() == "Darwin":  # macOS
    #         os.system("sudo shutdown -h now")
    #         return "💤 Выключаю компьютер."
    #     else:
    #         return "⚠️ Выключение не поддерживается на этой системе."
    # except Exception as e:
    #     return f"❌ Ошибка при выключении: {e}"
    return "Команда выключения получена (функция закомментирована и не выполняется!)."


def restart(*args, **kwargs):
    # """Перезагружает компьютер (кросс-платформенно)"""
    # try:
    #     if platform.system() == "Windows":
    #         os.system("shutdown /r /t 1")
    #         return "🔄 Перезагружаю компьютер через 1 секунду."
    #     elif platform.system() == "Linux":
    #         os.system("systemctl reboot")
    #         return "🔄 Перезагружаю компьютер."
    #     elif platform.system() == "Darwin":  # macOS
    #         os.system("sudo shutdown -r now")
    #         return "🔄 Перезагружаю компьютер."
    #     else:
    #         return "⚠️ Перезагрузка не поддерживается на этой системе."
    # except Exception as e:
    #     return f"❌ Ошибка при перезагрузке: {e}"
    return "Команда перезагрузки получена (функция закомментирована и не выполняется!)."


def sleep(*args, **kwargs):
    """Переводит компьютер в спящий режим (кросс-платформенно)"""
    try:
        if platform.system() == "Windows":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return "😴 Перевожу компьютер в спящий режим."
        elif platform.system() == "Linux":
            os.system("systemctl suspend")
            return "😴 Перевожу компьютер в спящий режим."
        elif platform.system() == "Darwin":  # macOS
            os.system("pmset sleepnow")
            return "😴 Перевожу компьютер в спящий режим."
        else:
            return "⚠️ Спящий режим не поддерживается на этой системе."
    except Exception as e:
        return f"❌ Ошибка при переходе в спящий режим: {e}"


def lock_screen(*args, **kwargs):
    """Блокирует экран компьютера"""
    try:
        if platform.system() == "Windows":
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return "🔒 Экран заблокирован."
        elif platform.system() == "Linux":
            # Пробуем разные команды для Linux
            os.system("gnome-screensaver-command -l || xdg-screensaver lock || loginctl lock-session")
            return "🔒 Экран заблокирован."
        elif platform.system() == "Darwin":  # macOS
            os.system("pmset displaysleepnow")
            return "🔒 Экран заблокирован."
        else:
            return "⚠️ Блокировка экрана не поддерживается на этой системе."
    except Exception as e:
        return f"❌ Ошибка при блокировке экрана: {e}"
