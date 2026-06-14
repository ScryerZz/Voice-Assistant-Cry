import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from src.skills import apps


class AppsSkillTests(unittest.TestCase):
    def test_open_app_resolves_alias_from_text_and_uses_argument_list(self):
        app_path = str(Path(__file__))
        config = {
            "apps": {
                "sample": {
                    "display_name": "Sample App",
                    "aliases": ["пример"],
                    "path": app_path,
                    "process": "sample.exe",
                }
            }
        }

        with patch("src.skills.apps.subprocess.Popen") as popen:
            response = apps.open_app(text="открой пример", config=config)

        self.assertIn("Sample App открыт", response)
        popen.assert_called_once_with([app_path], shell=False)

    def test_close_app_resolves_human_name_and_uses_taskkill_argument_list(self):
        config = {
            "apps": {
                "vscode": {
                    "display_name": "Visual Studio Code",
                    "aliases": ["код"],
                    "path": r"C:\Users\user\AppData\Local\Programs\Code\Code.exe",
                    "process": "Code.exe",
                }
            }
        }

        completed = subprocess.CompletedProcess(args=[], returncode=0)
        with (
            patch("src.skills.apps._is_windows", return_value=True),
            patch("src.skills.apps.subprocess.run", return_value=completed) as run,
        ):
            response = apps.close_app(text="закрой visual studio code", config=config)

        self.assertIn("Visual Studio Code закрыт", response)
        run.assert_called_once()
        call_args, call_kwargs = run.call_args
        self.assertEqual(call_args[0], ["taskkill", "/F", "/IM", "Code.exe"])
        self.assertEqual(call_kwargs["stdout"], apps.subprocess.DEVNULL)
        self.assertEqual(call_kwargs["stderr"], apps.subprocess.DEVNULL)
        self.assertFalse(call_kwargs["shell"])
        self.assertFalse(call_kwargs["check"])

    def test_open_app_missing_path_returns_message_without_launching(self):
        config = {
            "apps": {
                "notes": {
                    "display_name": "Заметки",
                    "aliases": ["заметки"],
                }
            }
        }

        with (
            patch("src.skills.apps._discover_app_path", return_value=None),
            patch("src.skills.apps.subprocess.Popen") as popen,
        ):
            response = apps.open_app(text="запусти заметки", config=config)

        self.assertIn("не настроен путь запуска", response)
        popen.assert_not_called()

    def test_close_app_missing_process_returns_message_without_taskkill(self):
        config = {
            "apps": {
                "notes": {
                    "display_name": "Заметки",
                    "aliases": ["заметки"],
                    "path": r"C:\Tools\notes.exe",
                }
            }
        }

        with patch("src.skills.apps.subprocess.run") as run:
            response = apps.close_app(text="закрой заметки", config=config)

        self.assertIn("не настроено имя процесса", response)
        run.assert_not_called()

    def test_app_status_reports_configured_path_and_running_process(self):
        config = {
            "apps": {
                "notes": {
                    "display_name": "Заметки",
                    "aliases": ["заметки"],
                    "path": str(Path(__file__)),
                    "process": "notes.exe",
                }
            }
        }

        with patch("src.skills.apps._is_process_running", return_value=True):
            response = apps.app_status(text="статус заметки", config=config)

        self.assertIn("Заметки", response)
        self.assertIn("путь запуска настроен", response)
        self.assertIn("процесс notes.exe запущен", response)

    def test_default_app_can_be_found_by_common_human_alias(self):
        self.assertEqual(apps.resolve_app_key("открой ворд"), "msword")


if __name__ == "__main__":
    unittest.main()
