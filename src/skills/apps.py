"""
Навык управления приложениями.
Открытие и закрытие популярных программ.
"""
import os
import subprocess
import shutil
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None


DEFAULT_APPS = {
    "telegram": {
        "display_name": "Telegram",
        "aliases": ["телеграм", "телега"],
        "process": "Telegram.exe",
        "candidates": ["Telegram.exe", "Telegram Desktop/Telegram.lnk"],
    },
    "yamusic": {
        "display_name": "Яндекс Музыка",
        "aliases": ["яндекс музыка", "яндексмузыка", "яндекс", "музыка"],
        "process": "Яндекс Музыка.exe",
        "candidates": ["Яндекс Музыка.lnk", "Yandex Music.lnk"],
    },
    "discord": {
        "display_name": "Discord",
        "aliases": ["дискорд"],
        "process": "Discord.exe",
        "candidates": ["Discord Inc/Discord.lnk", "Discord.exe"],
    },
    "steam": {
        "display_name": "Steam",
        "aliases": ["стим"],
        "process": "steam.exe",
        "candidates": ["Steam/steam.exe", "steam.exe"],
    },
    "flstudio": {
        "display_name": "FL Studio",
        "aliases": ["fl studio", "фл студио", "фл"],
        "process": "FL64.exe",
        "candidates": ["Image-Line/FL Studio 2024/FL64.exe", "FL64.exe"],
    },
    "msword": {
        "display_name": "Microsoft Word",
        "aliases": ["word", "ворд", "microsoft word"],
        "process": "WINWORD.EXE",
        "candidates": ["Microsoft Office/root/Office16/WINWORD.EXE", "WINWORD.EXE"],
    },
    "msexcel": {
        "display_name": "Microsoft Excel",
        "aliases": ["excel", "эксель", "microsoft excel"],
        "process": "EXCEL.EXE",
        "candidates": ["Microsoft Office/root/Office16/EXCEL.EXE", "EXCEL.EXE"],
    },
    "mspowerpoint": {
        "display_name": "Microsoft PowerPoint",
        "aliases": ["powerpoint", "power point", "поверпоинт", "презентации", "microsoft powerpoint"],
        "process": "POWERPNT.EXE",
        "candidates": ["Microsoft Office/root/Office16/POWERPNT.EXE", "POWERPNT.EXE"],
    }
}


def get_app_catalog(config: dict | None = None) -> dict[str, dict]:
    """Возвращает каталог приложений с учётом пользовательского конфига."""
    configured_apps = ((config or {}).get("apps") or {})
    catalog = {key: dict(value) for key, value in DEFAULT_APPS.items()}
    for key, value in configured_apps.items():
        app_info = dict(catalog.get(key, {}))
        app_info.update(value or {})
        catalog[key] = app_info
    return catalog


def resolve_app_key(app_name: str, config: dict | None = None) -> str | None:
    normalized = _normalize_app_name(app_name)
    if not normalized:
        return None

    contained_matches = []
    for key, app_info in get_app_catalog(config).items():
        for alias in _app_aliases(key, app_info):
            normalized_alias = _normalize_app_name(alias)
            if not normalized_alias:
                continue
            if normalized == normalized_alias:
                return key
            if len(normalized_alias) >= 3 and normalized_alias in normalized:
                contained_matches.append((len(normalized_alias), key))
    if contained_matches:
        return max(contained_matches, key=lambda item: item[0])[1]
    return None


def open_app(*args, **kwargs) -> str:
    """Открыть приложение по ключу, алиасу или названию из текста команды."""
    app_name = _requested_app_name(args, kwargs)
    if not app_name:
        return "Укажите, какое приложение открыть."
    return _open_app(app_name, **kwargs)


def close_app(*args, **kwargs) -> str:
    """Закрыть приложение по ключу, алиасу или названию из текста команды."""
    app_name = _requested_app_name(args, kwargs)
    if not app_name:
        return "Укажите, какое приложение закрыть."
    return _close_app(app_name, **kwargs)


def app_status(*args, **kwargs) -> str:
    """Проверить настройку и состояние приложения."""
    app_name = _requested_app_name(args, kwargs)
    if not app_name:
        return "Укажите приложение для проверки статуса."

    config = kwargs.get("config", {}) or {}
    resolved = _resolve_app(app_name, config)
    if not resolved:
        return f"Приложение '{app_name}' не найдено в настройках."

    key, app_info = resolved
    status = _app_status_record(key, app_info, include_process=True)
    display_name = status["display_name"]

    if status["path_source"] == "configured":
        path_text = "путь запуска настроен"
    elif status["path_source"] == "discovered":
        path_text = "путь запуска найден автоматически"
    elif status.get("configured_path"):
        path_text = "путь запуска настроен, но файл не найден"
    else:
        path_text = "путь запуска не настроен"

    process_name = status["process"]
    if not process_name:
        process_text = "имя процесса не настроено"
    elif status["process_running"] is True:
        process_text = f"процесс {process_name} запущен"
    elif status["process_running"] is False:
        process_text = f"процесс {process_name} не запущен"
    else:
        process_text = f"процесс {process_name}, статус запуска неизвестен"

    return f"{display_name}: {path_text}; {process_text}."


def _app_aliases(key: str, app_info: dict) -> list[str]:
    aliases = [key]
    for field in ("display_name", "name", "title", "human_name"):
        value = app_info.get(field)
        if value:
            aliases.append(str(value))

    process = str(app_info.get("process") or "").strip()
    if process:
        aliases.append(Path(process).stem)

    configured_aliases = app_info.get("aliases", []) or []
    if isinstance(configured_aliases, str):
        aliases.append(configured_aliases)
    else:
        aliases.extend(str(alias) for alias in configured_aliases if alias)
    return aliases


def _requested_app_name(args: tuple, kwargs: dict) -> str:
    for key in ("app_name", "app", "name", "query"):
        value = kwargs.get(key)
        if value:
            return str(value).strip()

    text = kwargs.get("text")
    if text:
        return str(text).strip()

    return " ".join(str(arg) for arg in args if isinstance(arg, str)).strip()


def _resolve_app(app_name: str, config: dict | None = None) -> tuple[str, dict] | None:
    resolved_key = resolve_app_key(app_name, config)
    if not resolved_key:
        return None

    app_info = get_app_catalog(config).get(resolved_key)
    if not app_info:
        return None
    return resolved_key, dict(app_info)


def _app_status_record(key: str, app_info: dict, include_process: bool = True) -> dict:
    configured_path = str(app_info.get("path") or "").strip()
    resolved_path = configured_path if configured_path and Path(configured_path).exists() else None
    discovered_path = None if resolved_path else _discover_app_path(app_info)
    path = resolved_path or discovered_path
    process_name = str(app_info.get("process") or "").strip()
    process_running = _is_process_running(process_name) if include_process and process_name else None

    if resolved_path:
        status = "ok"
        detail = "configured"
    elif configured_path and discovered_path:
        status = "ok"
        detail = f"configured path missing, discovered: {discovered_path}"
    elif discovered_path:
        status = "ok"
        detail = "discovered"
    elif configured_path:
        status = "warn"
        detail = f"configured path missing: {configured_path}"
    else:
        status = "warn"
        detail = "path not configured or discovered"

    return {
        "key": key,
        "display_name": app_info.get("display_name", key),
        "status": status,
        "path": path or "",
        "configured_path": configured_path,
        "path_source": "configured" if resolved_path else ("discovered" if discovered_path else "missing"),
        "process": process_name,
        "process_running": process_running,
        "details": detail,
    }


def _launch_app_path(path: str) -> None:
    if _is_windows() and Path(path).suffix.lower() in {".lnk", ".url"}:
        os.startfile(path)
        return
    subprocess.Popen([path], shell=False)


def _terminate_process(process_name: str):
    if _is_windows():
        return subprocess.run(
            ["taskkill", "/F", "/IM", process_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            check=False,
        )

    return subprocess.run(
        ["pkill", "-9", Path(process_name).stem],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        check=False,
    )


def _is_windows() -> bool:
    return os.name == "nt"


def get_app_statuses(config: dict | None = None, include_process: bool = True) -> list[dict]:
    """Возвращает статус путей и процессов приложений для UI/diagnostics."""
    statuses = []
    for key, app_info in get_app_catalog(config).items():
        statuses.append(_app_status_record(key, app_info, include_process=include_process))
    return statuses


def _open_app(app_name: str, **kwargs) -> str:
    """Универсальная функция открытия приложения"""
    app_info = _get_app_info(app_name, kwargs.get("config", {}))
    if not app_info:
        return f"Приложение '{app_name}' не найдено."

    configured_path = str(app_info.get("path") or "").strip()
    path = configured_path if configured_path and Path(configured_path).exists() else _discover_app_path(app_info)
    if not path:
        return f"Для {app_info.get('display_name', app_name)} не настроен путь запуска. Укажите путь в настройках приложения."
    
    try:
        _launch_app_path(str(path))
        return f"{app_info.get('display_name', app_name)} открыт."
    except Exception as e:
        return f"Ошибка при открытии {app_name}: {str(e)}"


def _close_app(app_name: str, **kwargs) -> str:
    """Универсальная функция закрытия приложения"""
    app_info = _get_app_info(app_name, kwargs.get("config", {}))
    if not app_info:
        return f"Приложение '{app_name}' не найдено."
    
    process_name = app_info.get("process")
    if not process_name:
        return f"Для {app_info.get('display_name', app_name)} не настроено имя процесса. Укажите процесс в настройках приложения."
    
    try:
        result = _terminate_process(str(process_name).strip())
        if result.returncode == 0:
            return f"{app_info.get('display_name', app_name)} закрыт."
        else:
            return f"{app_info.get('display_name', app_name)} не запущен или уже закрыт."
    except Exception as e:
        return f"Ошибка при закрытии {app_name}: {str(e)}"


def _get_app_info(app_name: str, config: dict) -> dict | None:
    resolved = _resolve_app(app_name, config)
    return resolved[1] if resolved else None


def _normalize_app_name(value: str) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def _discover_app_path(app_info: dict) -> str | None:
    candidates = list(app_info.get("candidates", []))
    process = app_info.get("process")
    if process:
        candidates.append(process)

    for candidate in candidates:
        direct = Path(candidate)
        if direct.exists():
            return str(direct)

        found = shutil.which(candidate)
        if found:
            return found

        for base in _windows_search_roots():
            path = base / candidate
            if path.exists():
                return str(path)
    return None


def _windows_search_roots() -> list[Path]:
    roots = []
    for env_name in ("APPDATA", "PROGRAMDATA", "ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        value = os.environ.get(env_name)
        if value:
            roots.append(Path(value))
            roots.append(Path(value) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return roots


def _is_process_running(process_name: str) -> bool | None:
    if not process_name or psutil is None:
        return None
    target = process_name.lower()
    try:
        for process in psutil.process_iter(["name"]):
            name = (process.info.get("name") or "").lower()
            if name == target:
                return True
    except Exception:
        return None
    return False


# === Telegram ===
def open_telegram(*args, **kwargs):
    """Открыть Telegram"""
    return _open_app("telegram", **kwargs)

def close_telegram(*args, **kwargs):
    """Закрыть Telegram"""
    return _close_app("telegram", **kwargs)


# === Яндекс Музыка ===
def open_yamusic(*args, **kwargs):
    """Открыть Яндекс Музыку"""
    return _open_app("yamusic", **kwargs)

def close_yamusic(*args, **kwargs):
    """Закрыть Яндекс Музыку"""
    return _close_app("yamusic", **kwargs)


# === Discord ===
def open_discord(*args, **kwargs):
    """Открыть Discord"""
    return _open_app("discord", **kwargs)

def close_discord(*args, **kwargs):
    """Закрыть Discord"""
    return _close_app("discord", **kwargs)


# === Steam ===
def open_steam(*args, **kwargs):
    """Открыть Steam"""
    return _open_app("steam", **kwargs)

def close_steam(*args, **kwargs):
    """Закрыть Steam"""
    return _close_app("steam", **kwargs)


# === FL Studio ===
def open_flstudio(*args, **kwargs):
    """Открыть FL Studio"""
    return _open_app("flstudio", **kwargs)

def close_flstudio(*args, **kwargs):
    """Закрыть FL Studio"""
    return _close_app("flstudio", **kwargs)


# === MS Word ===
def open_msword(*args, **kwargs):
    """Открыть Microsoft Word"""
    return _open_app("msword", **kwargs)

def close_msword(*args, **kwargs):
    """Закрыть Microsoft Word"""
    return _close_app("msword", **kwargs)


# === MS Excel ===
def open_msexcel(*args, **kwargs):
    """Открыть Microsoft Excel"""
    return _open_app("msexcel", **kwargs)

def close_msexcel(*args, **kwargs):
    """Закрыть Microsoft Excel"""
    return _close_app("msexcel", **kwargs)


# === MS PowerPoint ===
def open_mspowerpoint(*args, **kwargs):
    """Открыть Microsoft PowerPoint"""
    return _open_app("mspowerpoint", **kwargs)

def close_mspowerpoint(*args, **kwargs):
    """Закрыть Microsoft PowerPoint"""
    return _close_app("mspowerpoint", **kwargs)
