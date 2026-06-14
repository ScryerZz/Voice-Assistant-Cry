from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from src.core.config import EXECUTABLE_DIR, IS_FROZEN, PROJECT_ROOT


APP_NAME = "CryAssistant"
SHORTCUT_NAME = "CryAssistant.lnk"


@dataclass(frozen=True)
class AutostartResult:
    ok: bool
    message: str
    path: Path | None = None


def startup_shortcut_path() -> Path | None:
    startup_dir = _startup_dir()
    if not startup_dir:
        return None
    return startup_dir / SHORTCUT_NAME


def is_launch_on_login_enabled() -> bool:
    shortcut = startup_shortcut_path()
    return bool(shortcut and shortcut.exists())


def apply_startup_config(config: dict) -> AutostartResult:
    startup = config.get("startup", {}) if isinstance(config, dict) else {}
    enabled = bool(startup.get("launch_on_login", False))
    start_minimized = bool(startup.get("start_minimized_to_tray", True))
    return set_launch_on_login(enabled, start_minimized=start_minimized)


def set_launch_on_login(enabled: bool, start_minimized: bool = True) -> AutostartResult:
    if sys.platform != "win32":
        return AutostartResult(False, "Автозапуск поддерживается только в Windows.")

    shortcut = startup_shortcut_path()
    if not shortcut:
        return AutostartResult(False, "Не удалось найти папку автозагрузки Windows.")

    try:
        if not enabled:
            shortcut.unlink(missing_ok=True)
            return AutostartResult(True, "Автозапуск выключен.", shortcut)

        target, arguments, working_dir, icon = _launcher_command(start_minimized=start_minimized)
        shortcut.parent.mkdir(parents=True, exist_ok=True)

        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")
        link = shell.CreateShortcut(str(shortcut))
        link.TargetPath = str(target)
        link.Arguments = arguments
        link.WorkingDirectory = str(working_dir)
        link.Description = "Голосовой ассистент Cry"
        link.IconLocation = str(icon)
        link.Save()
        return AutostartResult(True, "Автозапуск включен.", shortcut)
    except Exception as exc:
        return AutostartResult(False, f"Не удалось обновить автозапуск: {exc}", shortcut)


def _startup_dir() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _launcher_command(start_minimized: bool) -> tuple[Path, str, Path, Path]:
    if IS_FROZEN:
        target = Path(sys.executable).resolve()
        arguments = "--minimized" if start_minimized else ""
        working_dir = EXECUTABLE_DIR
        return target, arguments, working_dir, target

    target = Path(sys.executable).resolve()
    ui_script = PROJECT_ROOT / "ui.py"
    arguments = f'"{ui_script}"'
    if start_minimized:
        arguments += " --minimized"
    return target, arguments, PROJECT_ROOT, target
