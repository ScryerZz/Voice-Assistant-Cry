import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from diagnose import (
    _check_ambiguous_command_patterns,
    _check_configured_apps,
    _check_config_yaml,
    _check_dangerous_action_coverage,
    _check_dependency_modules,
    _check_yaml,
    _check_log_secrets,
    _check_microphone_devices,
    _check_vosk_models,
    _diagnostic_import_modules,
    _print_checks,
)


class ConfiguredAppsDiagnosticsTests(unittest.TestCase):
    def test_empty_and_existing_paths_pass(self):
        with TemporaryDirectory() as tmpdir:
            app_path = Path(tmpdir) / "Demo.exe"
            app_path.write_text("", encoding="utf-8")

            name, ok, message = _check_configured_apps({
                "apps": {
                    "demo": {"path": str(app_path), "process": "Demo.exe"},
                    "optional": {"path": "", "process": "Optional.exe"},
                }
            })

        self.assertEqual(name, "Configured apps")
        self.assertTrue(ok)
        self.assertIn("paths existing=1", message)
        self.assertIn("empty=1", message)
        self.assertIn("processes valid=2", message)

    def test_missing_configured_path_warns_without_failing(self):
        with TemporaryDirectory() as tmpdir:
            missing_path = Path(tmpdir) / "Missing.exe"

            name, ok, message = _check_configured_apps({
                "apps": {
                    "missing": {"path": str(missing_path), "process": "Missing.exe"},
                }
            })

        self.assertEqual(name, "Configured apps")
        self.assertTrue(ok)
        self.assertIn("warnings: missing configured paths", message)
        self.assertIn("missing=", message)

    def test_invalid_process_name_fails(self):
        name, ok, message = _check_configured_apps({
            "apps": {
                "bad": {"path": "", "process": "notepad"},
            }
        })

        self.assertEqual(name, "Configured apps")
        self.assertFalse(ok)
        self.assertIn("invalid process values", message)
        self.assertIn("ending in .exe", message)


class DependencyDiagnosticsTests(unittest.TestCase):
    def test_dependency_check_reports_versions_without_importing_modules(self):
        with (
            patch("diagnose.importlib.util.find_spec", return_value=object()),
            patch("diagnose._package_version", return_value="1.2.3"),
        ):
            name, ok, message = _check_dependency_modules()

        self.assertEqual(name, "Python dependencies")
        self.assertTrue(ok)
        self.assertIn("versions:", message)
        self.assertIn("PyYAML=1.2.3", message)


class MicrophoneDiagnosticsTests(unittest.TestCase):
    def test_microphone_check_uses_query_devices_only(self):
        class FakeSoundDevice:
            class Default:
                device = [1, 3]

            default = Default()

            def __init__(self):
                self.query_count = 0

            def query_devices(self):
                self.query_count += 1
                return [
                    {"name": "Speakers", "max_input_channels": 0},
                    {"name": "USB Microphone", "max_input_channels": 2},
                ]

        fake = FakeSoundDevice()

        name, ok, message = _check_microphone_devices(fake)

        self.assertEqual(name, "Microphone devices")
        self.assertTrue(ok)
        self.assertEqual(fake.query_count, 1)
        self.assertIn("default_input=1", message)
        self.assertIn("USB Microphone", message)

    def test_microphone_check_warns_when_no_input_devices_are_reported(self):
        class FakeSoundDevice:
            def query_devices(self):
                return [{"name": "Speakers", "max_input_channels": 0}]

        name, ok, message = _check_microphone_devices(FakeSoundDevice())

        self.assertEqual(name, "Microphone devices")
        self.assertTrue(ok)
        self.assertIn("no input-capable devices", message)


class VoskDiagnosticsTests(unittest.TestCase):
    def _make_vosk_model(self, root: Path, folder: str):
        for relative in (
            Path("am") / "final.mdl",
            Path("conf") / "model.conf",
            Path("graph") / "HCLr.fst",
            Path("graph") / "Gr.fst",
        ):
            path = root / folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("ok", encoding="utf-8")

    def test_vosk_check_uses_legacy_models_when_configured_path_is_empty(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_vosk_model(root / "data" / "models", "vosk-model-small-ru-0.22")
            self._make_vosk_model(root / "data" / "models", "vosk-model-small-en-us-0.15")
            config = {
                "paths": {"stt_models": "data/models/stt"},
                "assistant": {"default_language": "ru"},
                "offline_mode": True,
                "auto_switch_mode": False,
            }
            with patch("diagnose.PROJECT_ROOT", root):
                name, ok, message = _check_vosk_models(config)

        self.assertEqual(name, "Vosk models")
        self.assertTrue(ok)
        self.assertIn("legacy", message)

    def test_vosk_check_fails_for_missing_default_model_in_strict_offline_mode(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = {
                "paths": {"stt_models": "data/models/stt"},
                "assistant": {"default_language": "ru"},
                "offline_mode": True,
                "auto_switch_mode": False,
            }
            with patch("diagnose.PROJECT_ROOT", root):
                name, ok, message = _check_vosk_models(config)

        self.assertEqual(name, "Vosk models")
        self.assertFalse(ok)
        self.assertIn("missing default-language offline model", message)


class CommandSafetyDiagnosticsTests(unittest.TestCase):
    def test_dangerous_action_coverage_fails_for_uncovered_destructive_action(self):
        records = [
            {
                "pattern": "shutdown computer",
                "normalized": "shutdown computer",
                "group": "skills",
                "key": "system",
                "action": "system.shutdown",
            },
            {
                "pattern": "clear notes",
                "normalized": "clear notes",
                "group": "skills",
                "key": "notes",
                "action": "notes.clear_notes",
            },
        ]
        config = {"safety": {"dangerous_actions": ["system.shutdown"]}}

        name, ok, message = _check_dangerous_action_coverage(config, records)

        self.assertEqual(name, "command conflicts: dangerous action coverage")
        self.assertFalse(ok)
        self.assertIn("notes.clear_notes", message)

    def test_dangerous_action_coverage_reports_unused_config_entries(self):
        records = [
            {
                "pattern": "shutdown computer",
                "normalized": "shutdown computer",
                "group": "skills",
                "key": "system",
                "action": "system.shutdown",
            },
        ]
        config = {
            "safety": {
                "dangerous_actions": [
                    "system.shutdown",
                    "system_control.clear_temp",
                ]
            }
        }

        name, ok, message = _check_dangerous_action_coverage(config, records)

        self.assertEqual(name, "command conflicts: dangerous action coverage")
        self.assertTrue(ok)
        self.assertIn("unused dangerous config actions", message)
        self.assertIn("system_control.clear_temp", message)

    def test_ambiguous_command_patterns_are_reported_as_warning(self):
        records = [
            {
                "pattern": "clear note",
                "normalized": "clear note",
                "group": "skills",
                "key": "notes",
                "action": "notes.clear_note",
            },
            {
                "pattern": "clear notes",
                "normalized": "clear notes",
                "group": "skills",
                "key": "notes",
                "action": "notes.clear_notes",
            },
        ]

        name, ok, message = _check_ambiguous_command_patterns(records)

        self.assertEqual(name, "command warnings: ambiguous fuzzy patterns")
        self.assertTrue(ok)
        self.assertIn("clear note", message)
        self.assertIn("clear notes", message)


class LogSecretDiagnosticsTests(unittest.TestCase):
    def test_log_secret_check_fails_without_printing_secret_value(self):
        with TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            secret = "SECRET-123456"
            (log_dir / "assistant.log").write_text(f"leaked {secret}", encoding="utf-8")
            config = {
                "logging": {"dir": str(log_dir), "file": "assistant.log"},
                "assistant": {"yandexgpt_api_key": secret},
            }

            name, ok, message = _check_log_secrets(config)

        self.assertEqual(name, "Log secrets")
        self.assertFalse(ok)
        self.assertIn("assistant.yandexgpt_api_key", message)
        self.assertNotIn(secret, message)

    def test_log_secret_check_passes_without_configured_secrets(self):
        name, ok, message = _check_log_secrets({"assistant": {"yandexgpt_api_key": ""}})

        self.assertEqual(name, "Log secrets")
        self.assertTrue(ok)
        self.assertIn("no configured secrets", message)


class OptionalUserCommandsDiagnosticsTests(unittest.TestCase):
    def test_user_commands_yaml_is_optional_on_clean_install(self):
        with patch("diagnose.pathlib.Path.exists", return_value=False):
            name, ok, message = _check_yaml("data/user_commands.yaml")

        self.assertEqual(name, "data/user_commands.yaml")
        self.assertTrue(ok)
        self.assertIn("optional", message)


class FrozenConfigDiagnosticsTests(unittest.TestCase):
    def test_frozen_config_check_uses_bundled_fallback_when_user_config_is_missing(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bundled_config = root / "data" / "config.yaml"
            bundled_config.parent.mkdir(parents=True)
            bundled_config.write_text("assistant:\n  name: Cry\n", encoding="utf-8")
            user_config = root / "user" / "data" / "config.yaml"

            with (
                patch("diagnose.IS_FROZEN", True),
                patch("diagnose.BUNDLE_DIR", root),
            ):
                name, ok, message = _check_config_yaml(user_config)

        self.assertEqual(name, "config.yaml")
        self.assertTrue(ok)
        self.assertIn("bundled fallback", message)

    def test_print_checks_does_not_fail_when_stdout_is_unavailable(self):
        checks = [("demo", True, "ok")]

        with (
            patch("builtins.print", side_effect=OSError("stdout unavailable")),
            patch("diagnose._write_diagnostic_report") as write_report,
        ):
            exit_code = _print_checks(checks)

        self.assertEqual(exit_code, 0)
        write_report.assert_called_once()

    def test_frozen_import_check_uses_runtime_modules(self):
        with patch("diagnose.IS_FROZEN", True):
            modules = _diagnostic_import_modules()

        self.assertIn("src.core.recognizer", modules)
        self.assertIn("src.ui.config_app", modules)
        self.assertNotIn("ui", modules)
        self.assertFalse(any(module.startswith("src.utils") for module in modules))


if __name__ == "__main__":
    unittest.main()
