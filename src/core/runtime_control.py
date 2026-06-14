from __future__ import annotations

import json

from src.core.config import resolve_runtime_path

RUNTIME_DIR = resolve_runtime_path("user:data/runtime", base="user")
CONTROL_FILE = RUNTIME_DIR / "control.json"


def read_control() -> dict:
    if not CONTROL_FILE.exists():
        return {}
    try:
        return json.loads(CONTROL_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_control(values: dict):
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    current = read_control()
    current.update(values)
    CONTROL_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def is_voice_listening_enabled(default: bool = True) -> bool:
    return bool(read_control().get("voice_listening_enabled", default))


def set_voice_listening_enabled(enabled: bool):
    write_control({"voice_listening_enabled": bool(enabled)})
