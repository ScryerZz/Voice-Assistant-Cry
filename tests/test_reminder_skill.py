import unittest
from datetime import datetime, timedelta

from src.skills.reminder import parse_reminder_time, set_reminder


class FakeStorage:
    def __init__(self):
        self.reminders = []

    def add_reminder(self, kind, text, due_at):
        self.reminders.append({"kind": kind, "text": text, "due_at": due_at})
        return len(self.reminders)


class ReminderTimeParserTests(unittest.TestCase):
    def test_parse_supported_ru_and_en_time_phrases(self):
        now = datetime(2026, 6, 4, 17, 0, 0)
        cases = [
            ("через 10 минут", now + timedelta(minutes=10)),
            ("через 2 часа", now + timedelta(hours=2)),
            ("через полчаса", now + timedelta(minutes=30)),
            ("завтра в 18:30", datetime(2026, 6, 5, 18, 30, 0)),
            ("сегодня в 18:30", datetime(2026, 6, 4, 18, 30, 0)),
            ("в 18:30", datetime(2026, 6, 4, 18, 30, 0)),
            ("in 10 minutes", now + timedelta(minutes=10)),
            ("tomorrow at 18:30", datetime(2026, 6, 5, 18, 30, 0)),
        ]

        for phrase, expected_due_at in cases:
            with self.subTest(phrase=phrase):
                parsed = parse_reminder_time(f"Напомни {phrase} Купить Молоко", now=now)

                self.assertEqual(parsed.due_at, expected_due_at)
                self.assertEqual(parsed.matched_text.lower(), phrase.lower())

    def test_bare_time_rolls_to_tomorrow_when_today_time_has_passed(self):
        now = datetime(2026, 6, 4, 19, 0, 0)

        parsed = parse_reminder_time("Напомни в 18:30 Купить Молоко", now=now)

        self.assertEqual(parsed.due_at, datetime(2026, 6, 5, 18, 30, 0))


class SetReminderTests(unittest.TestCase):
    def test_set_reminder_stores_due_at_and_preserves_reminder_text_case(self):
        now = datetime(2026, 6, 4, 17, 0, 0)
        storage = FakeStorage()

        response = set_reminder(text="Напомни через 10 минут Позвонить Маме", storage=storage, now=now)

        self.assertIn("Позвонить Маме", response)
        self.assertEqual(
            storage.reminders,
            [
                {
                    "kind": "reminder",
                    "text": "Позвонить Маме",
                    "due_at": now + timedelta(minutes=10),
                }
            ],
        )

    def test_set_reminder_stores_absolute_english_time_without_waiting(self):
        now = datetime(2026, 6, 4, 17, 0, 0)
        storage = FakeStorage()

        set_reminder(text="Remind me tomorrow at 18:30 to Call Mom", storage=storage, now=now)

        self.assertEqual(storage.reminders[0]["text"], "Call Mom")
        self.assertEqual(storage.reminders[0]["due_at"], datetime(2026, 6, 5, 18, 30, 0))

    def test_set_reminder_uses_five_minute_default_when_time_is_missing(self):
        now = datetime(2026, 6, 4, 17, 0, 0)
        storage = FakeStorage()

        set_reminder(text="Напомни Купить Молоко", storage=storage, now=now)

        self.assertEqual(storage.reminders[0]["text"], "Купить Молоко")
        self.assertEqual(storage.reminders[0]["due_at"], now + timedelta(minutes=5))


if __name__ == "__main__":
    unittest.main()
