from __future__ import annotations

import ast
import importlib
import importlib.metadata
import importlib.util
import pathlib
import re
import sys

from src.core.config import BUNDLE_DIR, IS_FROZEN, PROJECT_ROOT, USER_DATA_DIR, resolve_runtime_path

DANGEROUS_ACTION_TERMS = ("delete", "clear", "close", "shutdown", "restart", "sleep", "clean")
AMBIGUOUS_PATTERN_SCORE = 92
MAX_DIAGNOSTIC_EXAMPLES = 6
SYSTEM_DANGEROUS_ACTIONS = {"system.shutdown", "system.restart", "system.sleep"}
REQUIRED_MODULES = {
    "yaml": "PyYAML",
    "rapidfuzz": "rapidfuzz",
    "requests": "requests",
    "numpy": "numpy",
    "scipy": "scipy",
    "sounddevice": "sounddevice",
    "speech_recognition": "SpeechRecognition",
    "vosk": "vosk",
    "torch": "torch",
    "pyttsx3": "pyttsx3",
    "soundfile": "soundfile",
    "psutil": "psutil",
    "pyautogui": "pyautogui",
    "win32api": "pywin32",
    "pycaw": "pycaw",
    "deep_translator": "deep-translator",
}

VOSK_MODELS = {
    "ru": "vosk-model-small-ru-0.22",
    "en": "vosk-model-small-en-us-0.15",
}

VOSK_REQUIRED_FILES = (
    ("am", "final.mdl"),
    ("conf", "model.conf"),
    ("graph", "HCLr.fst"),
    ("graph", "Gr.fst"),
)

SILERO_MODELS = {
    "ru": "v3_1_ru.pt",
    "en": "v3_en.pt",
}


def main() -> int:
    _configure_console_encoding()

    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python", True, sys.version.split()[0]))
    checks.append(_check_dependency_modules())
    checks.append(_check_microphone_devices())

    try:
        from src.core.config import get_settings

        settings = get_settings()
        checks.append(("config.yaml", isinstance(settings.config, dict), "loaded"))
        checks.append(("commands.yaml", isinstance(settings.dataset, dict), "loaded"))
    except Exception as exc:
        checks.append(("config load", False, f"{type(exc).__name__}: {exc}"))
        return _print_checks(checks)

    checks.append(_check_config_yaml(settings.config_path))
    checks.append(_check_yaml(str(settings.dataset_path), optional=False, label="commands.yaml"))
    checks.append(_check_yaml(str(settings.user_commands_path), optional=True, label="user_commands.yaml"))
    checks.append(_check_runtime_paths(settings.config))
    checks.append(_check_configured_apps(settings.config))
    checks.append(_check_vosk_models(settings.config))
    checks.append(_check_silero_models(settings.config))
    checks.extend(_check_command_conflicts(settings.config, settings.dataset))
    checks.append(_check_actions(settings.dataset))
    checks.append(_check_matcher(settings.config, settings.dataset))
    checks.append(_check_chat_executor(settings.config, settings.dataset))
    checks.append(_check_ui_lifecycle())
    checks.append(_check_imports())
    checks.append(_check_storage(settings.config))
    checks.append(_check_history(settings.config))
    checks.append(_check_runtime_control())
    checks.append(_check_log_file(settings.config))
    checks.append(_check_log_secrets(settings.config))

    return _print_checks(checks)


def _print_checks(checks: list[tuple[str, bool, str]]) -> int:
    failed = False
    lines = []
    for name, ok, message in checks:
        status = "OK" if ok else "FAIL"
        lines.append(f"[{status}] {name}: {message}")
        failed = failed or not ok
    _write_diagnostic_report(lines)
    for line in lines:
        try:
            print(line)
        except (OSError, ValueError):
            break
    return 1 if failed else 0


def _write_diagnostic_report(lines: list[str]) -> None:
    try:
        report_path = resolve_runtime_path("user:data/runtime/diagnose-last.txt", base="user")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def _configure_console_encoding() -> None:
    try:
        from src.core.console import configure_console_encoding

        configure_console_encoding()
    except Exception:
        pass


def _check_yaml(path: str, optional: bool = False, label: str | None = None) -> tuple[str, bool, str]:
    label = label or path
    optional = optional or path.replace("\\", "/").endswith("data/user_commands.yaml")
    try:
        resolved = _project_path(path)
        if optional and not resolved.exists():
            return (label, True, "optional missing; will be created when the user adds phrases")
        import yaml

        data = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        return (label, isinstance(data, dict), f"{type(data).__name__}; {_relative(resolved)}")
    except Exception as exc:
        return (label, False, str(exc))


def _check_config_yaml(config_path: pathlib.Path) -> tuple[str, bool, str]:
    if IS_FROZEN and not config_path.exists():
        bundled_config = BUNDLE_DIR / "data" / "config.yaml"
        name, ok, message = _check_yaml(str(bundled_config), optional=False, label="config.yaml")
        if ok:
            return (name, True, f"bundled fallback; {message}")
        return (name, ok, message)
    return _check_yaml(str(config_path), optional=False, label="config.yaml")


def _check_dependency_modules() -> tuple[str, bool, str]:
    missing = []
    versions = []
    for module_name, package_name in REQUIRED_MODULES.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
            continue
        versions.append(f"{package_name}={_package_version(package_name)}")

    if missing:
        detail = "missing: " + ", ".join(missing)
        if versions:
            detail += "; installed: " + _with_extra_count(versions[:MAX_DIAGNOSTIC_EXAMPLES], len(versions))
        return ("Python dependencies", False, detail)
    return (
        "Python dependencies",
        True,
        f"{len(REQUIRED_MODULES)} modules available; versions: "
        + _with_extra_count(versions[:MAX_DIAGNOSTIC_EXAMPLES], len(versions)),
    )


def _package_version(package_name: str) -> str:
    candidates = {
        package_name,
        package_name.lower(),
        package_name.replace("_", "-"),
        package_name.lower().replace("_", "-"),
    }
    for candidate in candidates:
        try:
            return importlib.metadata.version(candidate)
        except importlib.metadata.PackageNotFoundError:
            continue
    return "unknown"


def _check_microphone_devices(sounddevice_module=None) -> tuple[str, bool, str]:
    try:
        if sounddevice_module is None:
            if importlib.util.find_spec("sounddevice") is None:
                return ("Microphone devices", True, "skipped: sounddevice module not installed")
            sounddevice_module = importlib.import_module("sounddevice")

        devices = sounddevice_module.query_devices()
    except Exception as exc:
        return ("Microphone devices", False, f"query_devices failed: {type(exc).__name__}: {exc}")

    input_devices = []
    for index, device in enumerate(devices or []):
        channels = _device_int(device, "max_input_channels")
        if channels <= 0:
            continue
        name = str(_device_value(device, "name", f"device-{index}")).strip() or f"device-{index}"
        input_devices.append(f"{index}:{name} ({channels}ch)")

    default_input = _default_input_device(sounddevice_module)
    default_note = f"default_input={default_input}; " if default_input is not None else ""

    if not input_devices:
        return (
            "Microphone devices",
            True,
            default_note + "warning: no input-capable devices reported by sounddevice.query_devices",
        )
    return (
        "Microphone devices",
        True,
        default_note
        + _with_extra_count(input_devices[:MAX_DIAGNOSTIC_EXAMPLES], len(input_devices)),
    )


def _device_value(device, key: str, default=None):
    if isinstance(device, dict):
        return device.get(key, default)
    return getattr(device, key, default)


def _device_int(device, key: str) -> int:
    try:
        return int(_device_value(device, key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _default_input_device(sounddevice_module):
    default = getattr(sounddevice_module, "default", None)
    device = getattr(default, "device", None)
    if isinstance(device, (list, tuple)) and device:
        return device[0]
    if isinstance(device, int):
        return device
    return None


def _check_runtime_paths(config: dict) -> tuple[str, bool, str]:
    paths = config.get("paths", {}) or {}
    important = {
        "datasets": (paths.get("datasets", "data/commands.yaml"), "bundle"),
        "user_commands": (paths.get("user_commands", "data/user_commands.yaml"), "user"),
        "database": (paths.get("database", "data/assistant.sqlite3"), "user"),
        "tts_models": (paths.get("tts_models", "data/models/tts"), "bundle"),
        "stt_models": (paths.get("stt_models", "data/models/stt"), "bundle"),
        "cache_dir": (paths.get("cache_dir", "data/cache"), "user"),
    }
    missing = []
    details = []
    for key, (raw_path, base) in important.items():
        path = _runtime_path(str(raw_path), base=base)
        if key == "datasets" and not path.exists():
            missing.append(f"{key}={path}")
        if key == "user_commands" and not path.exists():
            details.append(f"{key}={_relative(path)} (optional)")
        else:
            details.append(f"{key}={_relative(path)}")
    if missing:
        return ("Runtime paths", False, "missing: " + "; ".join(missing))
    return ("Runtime paths", True, "; ".join(details))


def _check_configured_apps(config: dict) -> tuple[str, bool, str]:
    apps = config.get("apps", {})
    if apps is None:
        apps = {}
    if not isinstance(apps, dict):
        return ("Configured apps", False, "config.apps must be a mapping")

    invalid_entries = []
    invalid_processes = []
    missing_paths = []
    existing_paths = 0
    empty_paths = 0
    valid_processes = 0

    for app_key, app_info in apps.items():
        key = str(app_key)
        if not isinstance(app_info, dict):
            invalid_entries.append(f"{key}={type(app_info).__name__}")
            continue

        path_value = str(app_info.get("path") or "").strip()
        if path_value:
            path = _project_path(path_value)
            if path.exists():
                existing_paths += 1
            else:
                missing_paths.append(f"{key}={path_value}")
        else:
            empty_paths += 1

        process_value = str(app_info.get("process") or "").strip()
        if _is_valid_app_process_name(process_value):
            valid_processes += 1
        else:
            invalid_processes.append(f"{key}={process_value!r}" if process_value else f"{key}=empty")

    if invalid_entries or invalid_processes:
        details = []
        if invalid_entries:
            details.append("invalid app entries: " + _with_extra_count(invalid_entries[:MAX_DIAGNOSTIC_EXAMPLES], len(invalid_entries)))
        if invalid_processes:
            details.append(
                "invalid process values: "
                + _with_extra_count(invalid_processes[:MAX_DIAGNOSTIC_EXAMPLES], len(invalid_processes))
                + ". Use a non-empty Windows image name ending in .exe, for example App.exe."
            )
        return ("Configured apps", False, " ".join(details))

    summary = f"paths existing={existing_paths}, empty={empty_paths}; processes valid={valid_processes}"
    if missing_paths:
        warnings = _with_extra_count(missing_paths[:MAX_DIAGNOSTIC_EXAMPLES], len(missing_paths))
        return (
            "Configured apps",
            True,
            f"warnings: missing configured paths: {warnings}. Empty paths are allowed; fix the path or leave it empty. {summary}",
        )
    return ("Configured apps", True, summary)


def _is_valid_app_process_name(process_name: str) -> bool:
    if not process_name or process_name.lower() == ".exe":
        return False
    if not process_name.lower().endswith(".exe"):
        return False
    return not any(separator in process_name for separator in ("/", "\\"))


def _check_vosk_models(config: dict) -> tuple[str, bool, str]:
    configured_root = _project_path(str((config.get("paths", {}) or {}).get("stt_models", "data/models/stt")))
    legacy_root = _bundle_root() / "data" / "models"
    results = []
    missing = []
    default_lang = str((config.get("assistant", {}) or {}).get("default_language", "ru"))
    strict_offline = bool(config.get("offline_mode")) and not bool(config.get("auto_switch_mode"))
    for lang, folder_name in VOSK_MODELS.items():
        model_path, source = _resolve_vosk_model_path(configured_root, legacy_root, folder_name)
        absent = _missing_vosk_model_files(model_path)
        if absent:
            missing.append(f"{lang}: {_relative(model_path)} missing {', '.join(absent)}")
        else:
            suffix = " legacy" if source == "legacy" else " configured"
            results.append(f"{lang}={_relative(model_path)} ({suffix.strip()})")

    note = f"; config stt_models={_relative(configured_root)}"
    if missing:
        default_missing = any(item.startswith(f"{default_lang}:") for item in missing)
        if strict_offline and default_missing:
            return (
                "Vosk models",
                False,
                "missing default-language offline model: " + "; ".join(missing) + note,
            )
        return ("Vosk models", True, "warnings: " + "; ".join(missing) + note)
    return ("Vosk models", True, ", ".join(results) + note)


def _resolve_vosk_model_path(
    configured_root: pathlib.Path,
    legacy_root: pathlib.Path,
    folder_name: str,
) -> tuple[pathlib.Path, str]:
    configured = configured_root / folder_name
    if not _missing_vosk_model_files(configured):
        return configured, "configured"

    legacy = legacy_root / folder_name
    if not _missing_vosk_model_files(legacy):
        return legacy, "legacy"

    return configured, "configured"


def _missing_vosk_model_files(model_path: pathlib.Path) -> list[str]:
    return [
        str(pathlib.Path(*parts))
        for parts in VOSK_REQUIRED_FILES
        if not (model_path / pathlib.Path(*parts)).exists()
    ]


def _check_silero_models(config: dict) -> tuple[str, bool, str]:
    model_root = _project_path(str((config.get("paths", {}) or {}).get("tts_models", "data/models/tts")))
    missing_or_empty = []
    ready = []
    for lang, filename in SILERO_MODELS.items():
        path = model_root / filename
        if not path.exists() or path.stat().st_size <= 0:
            missing_or_empty.append(f"{lang}={_relative(path)}")
        else:
            ready.append(f"{lang}={_relative(path)}")
    if missing_or_empty:
        return (
            "Silero models",
            True,
            "warnings: missing or empty " + ", ".join(missing_or_empty)
            + "; runtime may download or fallback to pyttsx3",
        )
    return ("Silero models", True, ", ".join(ready))


def _project_path(path_value: str) -> pathlib.Path:
    return _runtime_path(path_value, base="bundle")


def _runtime_path(path_value: str, base: str) -> pathlib.Path:
    raw = str(path_value or "").strip()
    path = pathlib.Path(raw)
    if path.is_absolute():
        return path
    if not IS_FROZEN and not raw.replace("\\", "/").startswith(("bundle:", "user:")):
        return PROJECT_ROOT / path
    return resolve_runtime_path(path_value, base=base)


def _relative(path: pathlib.Path) -> str:
    for root in (PROJECT_ROOT, BUNDLE_DIR, USER_DATA_DIR):
        try:
            return str(path.resolve().relative_to(root))
        except Exception:
            continue
    return str(path)


def _bundle_root() -> pathlib.Path:
    return BUNDLE_DIR if IS_FROZEN else PROJECT_ROOT


def _check_command_conflicts(config: dict, dataset: dict) -> list[tuple[str, bool, str]]:
    try:
        records = _command_pattern_records(config, dataset)
    except Exception as exc:
        return [("command conflicts", False, str(exc))]

    return [
        _check_duplicate_normalized_patterns(records),
        _check_ambiguous_command_patterns(records),
        _check_risky_one_word_patterns(records),
        _check_dangerous_action_coverage(config, records),
    ]


def _command_pattern_records(config: dict, dataset: dict) -> list[dict[str, str | None]]:
    from src.core.matcher import SmartMatcher

    matcher_config = config.get("matcher", {}) or {}
    matcher = SmartMatcher(
        dataset,
        threshold=int(matcher_config.get("threshold", config.get("matcher_threshold", 68))),
        config=config,
    )

    records = []
    for original, normalized, group, key, action, _response in matcher.patterns:
        records.append({
            "pattern": str(original),
            "normalized": str(normalized),
            "group": str(group),
            "key": str(key),
            "action": str(action) if action else None,
        })
    return records


def _check_duplicate_normalized_patterns(records: list[dict[str, str | None]]) -> tuple[str, bool, str]:
    by_normalized: dict[str, list[dict[str, str | None]]] = {}
    for record in records:
        normalized = record["normalized"]
        if not normalized:
            continue
        by_normalized.setdefault(normalized, []).append(record)

    conflicts = []
    harmless_duplicates = 0
    for normalized, duplicate_records in by_normalized.items():
        if len(duplicate_records) <= 1:
            continue
        targets = {
            record["action"] or f"{record['group']}.{record['key']}"
            for record in duplicate_records
        }
        if len(targets) > 1:
            conflicts.append((normalized, duplicate_records))
        else:
            harmless_duplicates += 1

    if not conflicts:
        suffix = f", {harmless_duplicates} same-target duplicates" if harmless_duplicates else ""
        return ("command conflicts: normalized duplicates", True, f"none{suffix}")

    examples = []
    for normalized, duplicate_records in conflicts[:MAX_DIAGNOSTIC_EXAMPLES]:
        locations = ", ".join(_format_command_record(record) for record in duplicate_records)
        examples.append(f"{normalized!r}: {locations}")
    return (
        "command conflicts: normalized duplicates",
        False,
        _with_extra_count(examples, len(conflicts)),
    )


def _check_risky_one_word_patterns(records: list[dict[str, str | None]]) -> tuple[str, bool, str]:
    risky = [
        record
        for record in records
        if record["group"] != "smalltalk"
        and record["normalized"]
        and len(str(record["normalized"]).split()) == 1
    ]
    if not risky:
        return ("command warnings: exact-only one-word patterns", True, "none")

    examples = [_format_command_record(record) for record in risky[:MAX_DIAGNOSTIC_EXAMPLES]]
    return (
        "command warnings: exact-only one-word patterns",
        True,
        f"{_with_extra_count(examples, len(risky))}. Fuzzy matching ignores these for multi-word phrases.",
    )


def _check_ambiguous_command_patterns(records: list[dict[str, str | None]]) -> tuple[str, bool, str]:
    try:
        from rapidfuzz import fuzz

        def similarity(left: str, right: str) -> float:
            return max(
                fuzz.ratio(left, right),
                fuzz.token_sort_ratio(left, right),
            )
    except Exception:
        from difflib import SequenceMatcher

        def similarity(left: str, right: str) -> float:
            sorted_left = " ".join(sorted(left.split()))
            sorted_right = " ".join(sorted(right.split()))
            return max(
                SequenceMatcher(None, left, right).ratio() * 100,
                SequenceMatcher(None, sorted_left, sorted_right).ratio() * 100,
            )

    ambiguous = []
    for index, left in enumerate(records):
        left_norm = str(left.get("normalized") or "")
        if len(left_norm) < 4:
            continue
        left_target = _record_target(left)
        for right in records[index + 1:]:
            right_norm = str(right.get("normalized") or "")
            if len(right_norm) < 4:
                continue
            right_target = _record_target(right)
            if left_target == right_target:
                continue
            score = similarity(left_norm, right_norm)
            if score >= AMBIGUOUS_PATTERN_SCORE:
                ambiguous.append(f"{left['pattern']!r}->{left_target} ~ {right['pattern']!r}->{right_target} ({round(score, 1)})")

    if not ambiguous:
        return ("command warnings: ambiguous fuzzy patterns", True, "none")
    return (
        "command warnings: ambiguous fuzzy patterns",
        True,
        _with_extra_count(ambiguous[:MAX_DIAGNOSTIC_EXAMPLES], len(ambiguous)),
    )


def _check_dangerous_action_coverage(config: dict, records: list[dict[str, str | None]]) -> tuple[str, bool, str]:
    covered_actions = {
        str(action)
        for action in ((config.get("safety", {}) or {}).get("dangerous_actions", []) or [])
    }
    command_actions = {
        str(record["action"])
        for record in records
        if record["action"]
    }
    uncovered = sorted(
        action
        for action in command_actions
        if _has_dangerous_action_term(action) and action not in covered_actions
    )
    if not uncovered:
        unused = sorted(covered_actions - command_actions)
        message = f"{len(covered_actions)} covered"
        if unused:
            message += "; unused dangerous config actions: " + _with_extra_count(unused[:MAX_DIAGNOSTIC_EXAMPLES], len(unused))
        return ("command conflicts: dangerous action coverage", True, message)

    examples = uncovered[:MAX_DIAGNOSTIC_EXAMPLES]
    return (
        "command conflicts: dangerous action coverage",
        False,
        _with_extra_count(examples, len(uncovered)),
    )


def _has_dangerous_action_term(action: str) -> bool:
    if action in SYSTEM_DANGEROUS_ACTIONS:
        return True
    module, _, function = action.partition(".")
    if module in {"logs", "history", "notes"} and function.startswith("clear"):
        return True
    if module == "system_control" and function.startswith(("clear", "clean")):
        return True
    if module == "apps" and function.startswith("close"):
        return True
    return False


def _format_command_record(record: dict[str, str | None]) -> str:
    return f"{record['pattern']!r}->{_record_target(record)}"


def _record_target(record: dict[str, str | None]) -> str:
    return str(record.get("action") or f"{record.get('group', '?')}.{record.get('key', '?')}")


def _with_extra_count(examples: list[str], total: int) -> str:
    message = "; ".join(examples)
    extra = total - len(examples)
    if extra > 0:
        message = f"{message}; +{extra} more"
    return message


def _check_actions(dataset: dict) -> tuple[str, bool, str]:
    funcs = {}
    for path in pathlib.Path("src/skills").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        funcs[path.stem] = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}

    actions = []
    for skill in (dataset.get("skills", {}) or {}).values():
        for command in (skill.get("commands", []) or []):
            action = str(command.get("action", "") or "")
            if re.match(r"^[A-Za-z_][\w]*\.[A-Za-z_][\w]*$", action):
                actions.append(action)

    missing = []
    for action in actions:
        module, function = action.split(".", 1)
        if module not in funcs or function not in funcs[module]:
            missing.append(action)

    if missing:
        return ("commands actions", False, ", ".join(missing))
    return ("commands actions", True, f"{len(actions)} actions")


def _check_imports() -> tuple[str, bool, str]:
    modules = _diagnostic_import_modules()

    errors = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")

    if errors:
        return ("imports", False, "; ".join(errors[:5]))
    return ("imports", True, f"{len(modules)} modules")


def _diagnostic_import_modules() -> list[str]:
    if IS_FROZEN:
        return [
            "diagnose",
            "main",
            "src.core.config",
            "src.core.executor",
            "src.core.matcher",
            "src.core.recognizer",
            "src.core.skill_manager",
            "src.core.storage",
            "src.core.tts",
            "src.ui.config_app",
            "src.ui.tray",
        ]

    modules = []
    for path in pathlib.Path("src").rglob("*.py"):
        if path.name != "__init__.py":
            modules.append(".".join(path.with_suffix("").parts))
    modules.extend(["main", "ui"])
    return modules


def _check_matcher(config: dict, dataset: dict) -> tuple[str, bool, str]:
    try:
        from src.core.matcher import SmartMatcher

        matcher_config = config.get("matcher", {}) or {}
        matcher = SmartMatcher(
            dataset,
            threshold=int(matcher_config.get("threshold", config.get("matcher_threshold", 68))),
            config=config,
        )
        cases = {
            "край пожалуйста открой браузер": "system.open_browser",
            "ну можешь показать последние команды": "history.recent_history",
            "очисти историю команд": "history.clear_history",
        }
        failures = []
        for phrase, expected_action in cases.items():
            matches = matcher.find_matches(phrase)
            action = matches[0].get("action") if matches else None
            if action != expected_action:
                failures.append(f"{phrase!r} -> {action!r}")
        if failures:
            return ("matcher", False, "; ".join(failures))
        return ("matcher", True, f"{len(cases)} smoke cases")
    except Exception as exc:
        return ("matcher", False, str(exc))


def _check_chat_executor(config: dict, dataset: dict) -> tuple[str, bool, str]:
    try:
        from src.core.executor import Executor
        from src.core.skill_manager import SkillManager
        from src.core.storage import AssistantStorage

        test_config = dict(config)
        test_config["debug"] = False
        storage = AssistantStorage(":memory:")
        skills = SkillManager(debug=False, context={
            "config": test_config,
            "dataset": dataset,
            "storage": storage,
            "chat_mode": True,
            "workers": [],
        })
        executor = Executor(dataset, skills, config=test_config)
        response = executor.handle("что ты умеешь", lang=test_config.get("assistant", {}).get("default_language", "ru"))
        if not response:
            return ("chat executor", False, "empty response")
        return ("chat executor", True, executor.last_trace.get("status", "unknown"))
    except Exception as exc:
        return ("chat executor", False, str(exc))


def _check_ui_lifecycle() -> tuple[str, bool, str]:
    root = None
    try:
        import tkinter as tk

        from src.ui.config_app import ConfigApp, FirstRunWizard

        root = tk.Tk()
        root.withdraw()
        app = ConfigApp(root)
        root.update_idletasks()

        issues = []
        notebook = getattr(app, "notebook", None)
        if notebook is None:
            issues.append("missing notebook")
        elif not notebook.select():
            issues.append("no selected notebook tab")

        nav_buttons = getattr(app, "nav_buttons", None)
        if not nav_buttons:
            issues.append("no nav buttons")
        else:
            missing_widgets = [
                button
                for _tab, button in nav_buttons
                if not hasattr(button, "winfo_exists") or not button.winfo_exists()
            ]
            if missing_widgets:
                issues.append(f"{len(missing_widgets)} nav button widgets not created")

        for widget_name in ("apps_tree", "notes_tree", "reminders_tree"):
            if not hasattr(app, widget_name):
                issues.append(f"missing {widget_name}")

        wizard = FirstRunWizard(app)
        wizard.update_idletasks()
        if not hasattr(wizard, "preflight_tree"):
            issues.append("first-run wizard missing preflight tree")
        if not wizard._collect_preflight_rows():
            issues.append("first-run wizard preflight rows empty")
        wizard.destroy()

        if issues:
            return ("UI lifecycle", False, "; ".join(issues))
        return ("UI lifecycle", True, f"selected notebook tab, {len(nav_buttons or [])} nav buttons, first-run wizard")
    except Exception as exc:
        return ("UI lifecycle", False, f"{type(exc).__name__}: {exc}")
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass


def _check_storage(config: dict) -> tuple[str, bool, str]:
    try:
        from src.core.storage import AssistantStorage

        storage = AssistantStorage(config.get("paths", {}).get("database"))
        count = storage.count_notes()
        return ("SQLite storage", True, f"notes={count}")
    except Exception as exc:
        return ("SQLite storage", False, str(exc))


def _check_history(config: dict) -> tuple[str, bool, str]:
    try:
        from src.core.storage import AssistantStorage

        storage = AssistantStorage(config.get("paths", {}).get("database"))
        count = storage.count_command_history()
        latest = storage.list_command_history(limit=1)
        source = latest[0].get("source", "voice") if latest else "none"
        return ("Command history", True, f"entries={count}, latest_source={source}")
    except Exception as exc:
        return ("Command history", False, str(exc))


def _check_runtime_control() -> tuple[str, bool, str]:
    try:
        from src.core.runtime_control import is_voice_listening_enabled

        enabled = is_voice_listening_enabled(default=True)
        return ("Runtime control", True, f"voice_listening_enabled={enabled}")
    except Exception as exc:
        return ("Runtime control", False, str(exc))


def _check_log_file(config: dict) -> tuple[str, bool, str]:
    try:
        from src.core.logs import get_log_file

        log_file = get_log_file(config)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        return ("Log file", True, str(log_file))
    except Exception as exc:
        return ("Log file", False, str(exc))


def _check_log_secrets(config: dict) -> tuple[str, bool, str]:
    try:
        secret_values = _collect_secret_values(config)
        if not secret_values:
            return ("Log secrets", True, "no configured secrets to scan")

        from src.core.logs import get_log_file

        log_file = get_log_file(config)
        log_files = [log_file, log_file.with_name("assistant_stdout.log")]
        leaked = []
        for path in log_files:
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            for label, value in secret_values:
                if value and value in content:
                    leaked.append(f"{path.name}:{label}")

        if leaked:
            return (
                "Log secrets",
                False,
                "secret values found in logs: " + _with_extra_count(sorted(set(leaked))[:MAX_DIAGNOSTIC_EXAMPLES], len(set(leaked))),
            )
        return ("Log secrets", True, f"scanned {len(log_files)} log files for {len(secret_values)} configured secrets")
    except Exception as exc:
        return ("Log secrets", False, str(exc))


def _collect_secret_values(config: dict) -> list[tuple[str, str]]:
    secret_terms = ("key", "token", "secret", "password")
    values = []

    def walk(node, path: tuple[str, ...] = ()):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, (*path, str(key)))
            return
        if not path or not any(term in path[-1].lower() for term in secret_terms):
            return
        value = str(node or "").strip()
        if len(value) >= 8:
            values.append((".".join(path), value))

    walk(config)
    return values


if __name__ == "__main__":
    raise SystemExit(main())
