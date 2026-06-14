import unittest

from src.core.support import (
    apply_assistant_profile,
    build_diagnostic_report,
    capture_assistant_profile,
    clear_config_secrets,
    make_profile_key,
    redact_config,
    secret_status_rows,
)


class SupportToolsTests(unittest.TestCase):
    def _config(self):
        return {
            "assistant": {
                "name": "Cry",
                "default_language": "ru",
                "personality": "friendly",
                "yandexgpt_api_key": "secret-yandex",
            },
            "voice_engine": "silero",
            "wake_word": "край",
            "weather": {"api_key": "secret-weather"},
            "news": {"api_key": "secret-news"},
            "privacy": {
                "redact_secrets_in_exports": True,
                "include_logs_in_reports": False,
                "include_history_in_reports": False,
            },
        }

    def test_redact_config_masks_api_keys(self):
        redacted = redact_config(self._config())

        self.assertEqual(redacted["assistant"]["yandexgpt_api_key"], "[скрыто]")
        self.assertEqual(redacted["weather"]["api_key"], "[скрыто]")
        self.assertEqual(redacted["news"]["api_key"], "[скрыто]")
        self.assertEqual(redacted["assistant"]["name"], "Cry")

    def test_profile_capture_excludes_secrets_and_can_apply(self):
        config = self._config()
        profile = capture_assistant_profile(config, "Дом")
        updated = apply_assistant_profile({"assistant": {"name": "Other"}}, profile)

        self.assertEqual(profile["label"], "Дом")
        self.assertNotIn("assistant.yandexgpt_api_key", profile["settings"])
        self.assertEqual(updated["assistant"]["name"], "Cry")
        self.assertEqual(updated["wake_word"], "край")

    def test_make_profile_key_is_unique(self):
        self.assertEqual(make_profile_key("Дом", {"дом"}), "дом_2")

    def test_secret_status_and_clear_config_secrets(self):
        rows = dict(secret_status_rows(self._config()))
        cleared = clear_config_secrets(self._config())

        self.assertTrue(rows["API-ключ ЯндексGPT"])
        self.assertEqual(cleared["assistant"]["yandexgpt_api_key"], "")
        self.assertEqual(cleared["weather"]["api_key"], "")
        self.assertEqual(cleared["news"]["api_key"], "")

    def test_diagnostic_report_redacts_secrets_by_default(self):
        report = build_diagnostic_report(
            self._config(),
            status_rows=[("Проверка", "ok", "secret-yandex не должен попасть в отчёт")],
            diagnostics_output="secret-weather",
        )

        self.assertNotIn("secret-yandex", report)
        self.assertNotIn("secret-weather", report)
        self.assertIn("[скрыто]", report)


if __name__ == "__main__":
    unittest.main()
