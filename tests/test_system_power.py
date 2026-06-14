import unittest
from unittest.mock import patch

from src.skills import system


class SystemPowerCommandTests(unittest.TestCase):
    def test_shutdown_uses_windows_shutdown_with_configured_delay(self):
        with (
            patch("src.skills.system.platform.system", return_value="Windows"),
            patch("src.skills.system.subprocess.run") as run,
        ):
            response = system.shutdown(config={"system_power": {"shutdown_delay_seconds": 45}})

        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(command[:5], ["shutdown.exe", "/s", "/t", "45", "/c"])
        self.assertIn("Выключение запланировано через 45 секунд", response)
        self.assertIn("отмени выключение", response)

    def test_restart_uses_windows_shutdown_restart_flag(self):
        with (
            patch("src.skills.system.platform.system", return_value="Windows"),
            patch("src.skills.system.subprocess.run") as run,
        ):
            response = system.restart(config={"system_power": {"shutdown_delay_seconds": 20}})

        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(command[:5], ["shutdown.exe", "/r", "/t", "20", "/c"])
        self.assertIn("Перезагрузка запланирована через 20 секунд", response)
        self.assertIn("отмени перезагрузку", response)

    def test_power_delay_is_clamped_to_safe_minimum(self):
        with (
            patch("src.skills.system.platform.system", return_value="Windows"),
            patch("src.skills.system.subprocess.run") as run,
        ):
            system.shutdown(config={"system_power": {"shutdown_delay_seconds": 1}})

        self.assertEqual(run.call_args.args[0][3], "5")

    def test_cancel_shutdown_uses_abort_flag(self):
        with (
            patch("src.skills.system.platform.system", return_value="Windows"),
            patch("src.skills.system.subprocess.run") as run,
        ):
            response = system.cancel_shutdown()

        run.assert_called_once_with(["shutdown.exe", "/a"], check=True, capture_output=True, text=True)
        self.assertIn("отменены", response)


if __name__ == "__main__":
    unittest.main()
