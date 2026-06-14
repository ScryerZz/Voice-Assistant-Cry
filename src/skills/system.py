import os
import webbrowser
import platform
import subprocess


DEFAULT_POWER_DELAY_SECONDS = 30
MIN_POWER_DELAY_SECONDS = 5
MAX_POWER_DELAY_SECONDS = 600


def _power_delay_seconds(config: dict | None) -> int:
    power_config = (config or {}).get("system_power", {})
    try:
        delay = int(power_config.get("shutdown_delay_seconds", DEFAULT_POWER_DELAY_SECONDS))
    except (TypeError, ValueError):
        delay = DEFAULT_POWER_DELAY_SECONDS
    return max(MIN_POWER_DELAY_SECONDS, min(delay, MAX_POWER_DELAY_SECONDS))


def _run_command(command: list[str]) -> tuple[bool, str]:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        return True, ""
    except FileNotFoundError:
        return False, f"Команда не найдена: {command[0]}"
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "").strip()
        return False, message or str(exc)

def open_browser(*args, **kwargs):
    try:
        # cross-platform try
        webbrowser.open("https://www.google.com")
        return "Открываю браузер."
    except Exception as e:
        return f"Ошибка при открытии браузера: {e}"


def shutdown(*args, **kwargs):
    """Планирует выключение компьютера после safety-подтверждения."""
    system_name = platform.system()
    delay = _power_delay_seconds(kwargs.get("config"))

    if system_name == "Windows":
        ok, error = _run_command([
            "shutdown.exe",
            "/s",
            "/t",
            str(delay),
            "/c",
            "Cry Assistant: выключение подтверждено пользователем.",
        ])
        if ok:
            return f"Выключение запланировано через {delay} секунд. Чтобы отменить, скажите: отмени выключение."
        return f"Не удалось запланировать выключение: {error}"

    if system_name == "Linux":
        ok, error = _run_command(["systemctl", "poweroff"])
        return "Выключаю компьютер." if ok else f"Не удалось выключить компьютер: {error}"

    if system_name == "Darwin":
        ok, error = _run_command(["osascript", "-e", 'tell app "System Events" to shut down'])
        return "Выключаю компьютер." if ok else f"Не удалось выключить компьютер: {error}"

    return "Выключение не поддерживается на этой системе."


def restart(*args, **kwargs):
    """Планирует перезагрузку компьютера после safety-подтверждения."""
    system_name = platform.system()
    delay = _power_delay_seconds(kwargs.get("config"))

    if system_name == "Windows":
        ok, error = _run_command([
            "shutdown.exe",
            "/r",
            "/t",
            str(delay),
            "/c",
            "Cry Assistant: перезагрузка подтверждена пользователем.",
        ])
        if ok:
            return f"Перезагрузка запланирована через {delay} секунд. Чтобы отменить, скажите: отмени перезагрузку."
        return f"Не удалось запланировать перезагрузку: {error}"

    if system_name == "Linux":
        ok, error = _run_command(["systemctl", "reboot"])
        return "Перезагружаю компьютер." if ok else f"Не удалось перезагрузить компьютер: {error}"

    if system_name == "Darwin":
        ok, error = _run_command(["osascript", "-e", 'tell app "System Events" to restart'])
        return "Перезагружаю компьютер." if ok else f"Не удалось перезагрузить компьютер: {error}"

    return "Перезагрузка не поддерживается на этой системе."


def cancel_shutdown(*args, **kwargs):
    """Отменяет запланированное выключение или перезагрузку Windows."""
    if platform.system() != "Windows":
        return "Отмена запланированного выключения поддерживается только на Windows."

    ok, error = _run_command(["shutdown.exe", "/a"])
    if ok:
        return "Запланированное выключение или перезагрузка отменены."
    return f"Не удалось отменить выключение или перезагрузку: {error}"


def sleep(*args, **kwargs):
    """Переводит компьютер в спящий режим (кросс-платформенно)"""
    try:
        if platform.system() == "Windows":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return "Перевожу компьютер в спящий режим."
        elif platform.system() == "Linux":
            os.system("systemctl suspend")
            return "Перевожу компьютер в спящий режим."
        elif platform.system() == "Darwin":  # macOS
            os.system("pmset sleepnow")
            return "Перевожу компьютер в спящий режим."
        else:
            return "Спящий режим не поддерживается на этой системе."
    except Exception as e:
        return f"Ошибка при переходе в спящий режим: {e}"


def lock_screen(*args, **kwargs):
    """Блокирует экран компьютера"""
    try:
        if platform.system() == "Windows":
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return "Экран заблокирован."
        elif platform.system() == "Linux":
            # Пробуем разные команды для Linux
            os.system("gnome-screensaver-command -l || xdg-screensaver lock || loginctl lock-session")
            return "Экран заблокирован."
        elif platform.system() == "Darwin":  # macOS
            os.system("pmset displaysleepnow")
            return "Экран заблокирован."
        else:
            return "Блокировка экрана не поддерживается на этой системе."
    except Exception as e:
        return f"Ошибка при блокировке экрана: {e}"
