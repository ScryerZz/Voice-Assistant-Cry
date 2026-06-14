from __future__ import annotations

import threading
import time

from src.core.storage import AssistantStorage


class ReminderScheduler:
    def __init__(self, storage: AssistantStorage, tts=None, interval: float = 5.0):
        self.storage = storage
        self.tts = tts
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="reminder_scheduler")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def join(self, timeout: float | None = None):
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self):
        while not self._stop.is_set():
            try:
                due = self.storage.due_reminders()
                if due:
                    for item in due:
                        prefix = "Таймер завершён" if item["kind"] == "timer" else "Напоминание"
                        message = f"{prefix}: {item['text']}"
                        if self.tts:
                            self.tts.speak(message, lang="ru")
                        else:
                            print(message)
                    self.storage.complete_reminders(item["id"] for item in due)
            except Exception as exc:
                print(f"[ReminderScheduler] {exc}")
            self._stop.wait(self.interval)
