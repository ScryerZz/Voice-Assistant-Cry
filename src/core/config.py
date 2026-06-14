from __future__ import annotations

# src/core/config.py
import os
import sys
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from copy import deepcopy
from shutil import copy2

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
IS_FROZEN = bool(getattr(sys, "frozen", False))
EXECUTABLE_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else PROJECT_ROOT
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", EXECUTABLE_DIR if IS_FROZEN else PROJECT_ROOT)).resolve()


def _default_user_data_dir() -> Path:
    if not IS_FROZEN:
        return PROJECT_ROOT
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "CryAssistant"
    return EXECUTABLE_DIR


USER_DATA_DIR = Path(os.environ.get("CRY_ASSISTANT_DATA_DIR") or _default_user_data_dir()).resolve()

# BASE_DIR remains the development project root for compatibility. In frozen
# builds it points to writable per-user data, while bundled assets live in
# BUNDLE_DIR and are resolved explicitly with base="bundle".
BASE_DIR = USER_DATA_DIR if IS_FROZEN else PROJECT_ROOT
DATA_PATH = BASE_DIR / "data"
DEFAULT_CONFIG_PATH = DATA_PATH / "config.yaml"
DATASET_PATH = (BUNDLE_DIR if IS_FROZEN else BASE_DIR) / "data" / "commands.yaml"
USER_COMMANDS_PATH = DATA_PATH / "user_commands.yaml"
MODELS_DIR = (BUNDLE_DIR if IS_FROZEN else BASE_DIR) / "data" / "models"

DEFAULT_CONFIG = {
    "voice_enabled": True,
    "voice_engine": "silero",
    "voice_speed": 180,
    "voice_volume": 1.0,
    "voice_gender": "female",
    "voice_speaker": "aidar",
    "language": "ru-RU",
    "wake_word": "край",
    "wake_words": {"ru": ["край"], "en": ["cry"]},
    "recognition": {
        "online_listen_seconds": 5,
        "offline_listen_timeout_seconds": 8,
        "audio_queue_timeout_seconds": 1.0,
        "recover_after_errors": 3,
        "miss_threshold": 3,
        "repeat_prompt_enabled": True,
    },
    "matcher": {
        "threshold": 68,
        "partial_threshold": 78,
        "smalltalk_threshold": 45,
        "min_partial_length": 5,
    },
    "assistant": {
        "name": "Cry",
        "default_language": "ru",
        "voice": "default",
        "personality": "friendly",
        "ai_enabled": False,
        "yandexgpt_api_key": "",
        "yandex_folder_id": "",
    },
    "debug": False,
    "logging": {
        "dir": "data/logs",
        "file": "assistant.log",
        "level": "INFO",
        "max_bytes": 1_000_000,
        "backup_count": 5,
    },
    "offline_mode": True,
    "auto_switch_mode": True,
    "first_run_completed": False,
    "startup": {
        "launch_on_login": False,
        "start_minimized_to_tray": True,
        "minimize_to_tray_on_close": True,
        "start_assistant_on_launch": False,
    },
    "privacy": {
        "redact_secrets_in_exports": True,
        "include_logs_in_reports": True,
        "include_history_in_reports": False,
        "crash_summary_lines": 80,
    },
    "profiles": {
        "active": "",
        "items": {},
    },
    "paths": {
        "datasets": "bundle:data/commands.yaml",
        "user_commands": "user:data/user_commands.yaml",
        "tts_models": "bundle:data/models/tts",
        "stt_models": "bundle:data/models/stt",
        "cache_dir": "user:data/cache",
        "database": "user:data/assistant.sqlite3",
    },
    "silero": {
        "ru_speakers": ["aidar", "baya", "kseniya", "xenia", "eugene"],
        "en_speakers": ["en_0", "en_1", "en_2"],
        "sample_rate": 48000,
        "use_cuda": True,
    },
    "weather": {"api_key": "", "default_city": "Казань"},
    "news": {"api_key": ""},
    "system_power": {
        "shutdown_delay_seconds": 30,
    },
    "safety": {
        "confirm_dangerous_commands": True,
        "confirmation_timeout_seconds": 15,
        "dangerous_min_score": 90,
        "dangerous_actions": [
            "system.shutdown",
            "system.restart",
            "system.sleep",
            "system_control.clear_recycle_bin",
            "system_control.clear_downloads",
            "system_control.clean_system",
            "system_control.clear_temp",
            "notes.clear_notes",
            "logs.clear_logs",
            "history.clear_history",
            "apps.close_app",
            "apps.close_telegram",
            "apps.close_yamusic",
            "apps.close_discord",
            "apps.close_steam",
            "apps.close_flstudio",
            "apps.close_msword",
            "apps.close_msexcel",
            "apps.close_mspowerpoint",
        ],
    },
    "apps": {},
}

@dataclass
class Settings:
    config_path: Path = DEFAULT_CONFIG_PATH
    dataset_path: Path = DATASET_PATH
    user_commands_path: Path = USER_COMMANDS_PATH
    config: dict = field(default_factory=dict)
    dataset: dict = field(default_factory=dict)

    def __post_init__(self):
        self.reload()

    def reload(self):
        loaded_config = self._safe_load(self.config_path) or {}
        if IS_FROZEN and not loaded_config:
            bundled_config = BUNDLE_DIR / "data" / "config.yaml"
            loaded_config = self._safe_load(bundled_config) or {}
        self.config = _deep_merge(deepcopy(DEFAULT_CONFIG), loaded_config)
        paths = self.config.get("paths", {}) or {}
        self.dataset_path = self._resolve_path(paths.get("datasets", self.dataset_path), base="bundle")
        self.user_commands_path = self._resolve_path(paths.get("user_commands", self.user_commands_path), base="user")
        base_dataset = self._safe_load(self.dataset_path) or {}
        user_dataset = self._safe_load(self.user_commands_path) or {}
        self.dataset = _merge_datasets(base_dataset, user_dataset)

    def _safe_load(self, path: Path):
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _resolve_path(self, path_value: str | Path, base: str = "user") -> Path:
        return resolve_runtime_path(path_value, base=base)

    def get(self, *keys, default=None):
        data = self.config
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k, default)
            else:
                return default
        return default if data is None else data

    def set(self, *keys, value):
        if not keys:
            raise ValueError("At least one config key is required")

        data = self.config
        for key in keys[:-1]:
            if not isinstance(data.get(key), dict):
                data[key] = {}
            data = data[key]
        data[keys[-1]] = value

    def update_config(self, values: dict):
        self.config = _deep_merge(deepcopy(self.config), values)

    def save(self, config: dict | None = None):
        if config is not None:
            self.config = deepcopy(config)

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if self.config_path.exists():
            copy2(self.config_path, self.config_path.with_suffix(".yaml.bak"))
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                self.config,
                f,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )


def _deep_merge(base: dict, updates: dict) -> dict:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def resolve_runtime_path(path_value: str | Path | None, *, base: str = "user") -> Path:
    """Resolve paths for both source runs and PyInstaller frozen builds.

    Supported prefixes:
    - bundle: files shipped with the app (commands, models, media).
    - user: writable per-user data (config, logs, database, runtime files).
    Relative paths without a prefix keep the old development behavior, but in
    frozen mode they are resolved from the requested base.
    """
    raw = str(path_value or "").strip()
    if not raw:
        root = USER_DATA_DIR if base == "user" else BUNDLE_DIR
        return root

    normalized = raw.replace("\\", "/")
    if normalized.startswith("bundle:"):
        return BUNDLE_DIR / normalized[len("bundle:"):].lstrip("/")
    if normalized.startswith("user:"):
        return USER_DATA_DIR / normalized[len("user:"):].lstrip("/")

    path = Path(raw)
    if path.is_absolute():
        return path

    if IS_FROZEN:
        root = BUNDLE_DIR if base == "bundle" else USER_DATA_DIR
    else:
        root = PROJECT_ROOT
    return root / path


def _merge_datasets(base_dataset: dict, user_dataset: dict) -> dict:
    merged = deepcopy(base_dataset or {})
    user_dataset = user_dataset or {}

    for section_key, section_value in user_dataset.items():
        if section_key != "skills":
            if isinstance(section_value, dict) and isinstance(merged.get(section_key), dict):
                merged[section_key] = _deep_merge(merged[section_key], deepcopy(section_value))
            else:
                merged[section_key] = deepcopy(section_value)

    merged.setdefault("skills", {})
    for skill_key, skill_data in (user_dataset.get("skills", {}) or {}).items():
        if not isinstance(skill_data, dict):
            continue
        target = merged["skills"].setdefault(skill_key, {})
        if skill_data.get("description"):
            target["description"] = skill_data.get("description")
        target.setdefault("commands", [])
        target["commands"].extend(deepcopy(skill_data.get("commands", []) or []))

    return merged


def get_settings():
    return Settings()

# import yaml
# from pathlib import Path
# from functools import lru_cache

# BASE_DIR = Path(__file__).resolve().parent.parent.parent
# DATA_PATH = BASE_DIR / "data"
# DEFAULT_CONFIG_PATH = DATA_PATH / "config.yaml"
# DATASET_PATH = DATA_PATH / "commands.yaml"
# MODELS_DIR = DATA_PATH / "models"

# class Settings:
#     def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH, dataset_path: Path = DATASET_PATH):
#         self.config_path = config_path
#         self.dataset_path = dataset_path
#         self.config = self.load_config(config_path)
#         self.dataset = self.load_dataset(dataset_path)

#     def load_config(self, path: Path):
#         if not path.exists():
#             print(f"[WARN] Config not found at {path}, using defaults.")
#             # Значения по умолчанию
#             return {
#                 "assistant": {"default_language": "ru"},
#                 "voice_enabled": True,
#                 "voice_engine": "silero",
#                 "voice_speed": 160,
#                 "voice_volume": 1.0,
#                 "voice_gender": "female",
#                 "voice_speaker": "aidar",
#                 "matcher_threshold": 60,
#                 "debug": False,
#                 "offline_mode": False,
#                 "auto_switch_mode": True,
#                 "wake_word": "край",
#             }
#         with open(path, "r", encoding="utf-8") as f:
#             cfg = yaml.safe_load(f)
#         # Проверка наличия необходимых ключей и настройка при их отсутствии:
#         cfg.setdefault("voice_enabled", True)
#         cfg.setdefault("voice_engine", "silero")
#         cfg.setdefault("voice_speed", 160)
#         cfg.setdefault("voice_volume", 1.0)
#         cfg.setdefault("offline_mode", False)
#         cfg.setdefault("auto_switch_mode", True)
#         cfg.setdefault("debug", False)
#         cfg.setdefault("matcher_threshold", 60)
#         cfg.setdefault("wake_word", "край")
#         return cfg
    
#     def load_dataset(self, path: Path):
#         if not path.exists():
#             raise FileNotFoundError(f"Dataset not found: {path}")
#         with open(path, "r", encoding="utf-8") as f:
#             return yaml.safe_load(f)

#     def get(self, *keys, default=None):
#         data = self.config
#         for k in keys:
#             if isinstance(data, dict) and k in data:
#                 data = data[k]
#             else:
#                 return default
#         return data

# # Убираем кеширование, чтобы перезагрузка конфига реально читала файл заново
# def get_settings(
#     config_path: Path = DEFAULT_CONFIG_PATH, 
#     dataset_path: Path = DATASET_PATH
# ):
#     return Settings(config_path=config_path, dataset_path=dataset_path)
