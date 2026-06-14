from __future__ import annotations

import shutil
import sys
from copy import deepcopy
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DATA = ROOT / "data"
RELEASE_DATA = ROOT / "build" / "release_data" / "data"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.config import DEFAULT_CONFIG


def _copy_file(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Required release file is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Required release directory is missing: {source}")
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def _clean_config() -> dict:
    config = deepcopy(DEFAULT_CONFIG)
    config["first_run_completed"] = False
    config["debug"] = False
    config["assistant"] = {
        **config.get("assistant", {}),
        "ai_enabled": False,
        "yandexgpt_api_key": "",
        "yandex_folder_id": "",
    }
    config["weather"] = {**config.get("weather", {}), "api_key": ""}
    config["news"] = {**config.get("news", {}), "api_key": ""}
    config["apps"] = {}
    return config


def main() -> int:
    if RELEASE_DATA.exists():
        shutil.rmtree(RELEASE_DATA)
    RELEASE_DATA.mkdir(parents=True, exist_ok=True)

    _copy_file(SOURCE_DATA / "commands.yaml", RELEASE_DATA / "commands.yaml")
    _copy_tree(SOURCE_DATA / "media", RELEASE_DATA / "media")
    _copy_tree(SOURCE_DATA / "models" / "stt", RELEASE_DATA / "models" / "stt")
    _copy_tree(SOURCE_DATA / "models" / "tts", RELEASE_DATA / "models" / "tts")

    (RELEASE_DATA / "user_commands.yaml").write_text("skills: {}\n", encoding="utf-8")
    (RELEASE_DATA / "config.yaml").write_text(
        yaml.safe_dump(_clean_config(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    for runtime_dir in ("cache", "logs", "runtime", "screenshots"):
        (RELEASE_DATA / runtime_dir).mkdir(parents=True, exist_ok=True)

    print(f"Release data prepared: {RELEASE_DATA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
