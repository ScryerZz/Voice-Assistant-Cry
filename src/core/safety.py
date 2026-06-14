from __future__ import annotations

import time


CONFIRM_WORDS = {
    "ru": {"подтверждаю", "да подтверждаю", "подтверждаю выполнение", "выполняй"},
    "en": {"confirm", "yes confirm", "confirm execution", "execute", "do it"},
}

CANCEL_WORDS = {
    "ru": {"отмена", "отмени", "не надо", "стоп", "нет"},
    "en": {"cancel", "stop", "no", "never mind"},
}


class ConfirmationManager:
    def __init__(self, config: dict):
        safety = (config or {}).get("safety", {})
        self.enabled = bool(safety.get("confirm_dangerous_commands", True))
        self.timeout = float(safety.get("confirmation_timeout_seconds", 15))
        self.dangerous_min_score = float(safety.get("dangerous_min_score", 90))
        self.dangerous_actions = set(safety.get("dangerous_actions", []))
        self.pending: dict | None = None

    def requires_confirmation(self, action: str | None) -> bool:
        return bool(self.enabled and action and action in self.dangerous_actions)

    def has_required_confidence(self, match: dict) -> bool:
        if not self.requires_confirmation(match.get("action")):
            return True
        try:
            score = float(match.get("score", 0) or 0)
        except (TypeError, ValueError):
            score = 0
        return score >= self.dangerous_min_score

    def set_pending(self, match: dict, text: str, lang: str, matches: list[dict] | None = None):
        dangerous_actions = [
            str(item.get("action"))
            for item in (matches or [match])
            if self.requires_confirmation(item.get("action"))
        ]
        self.pending = {
            "match": match,
            "matches": list(matches or [match]),
            "dangerous_actions": dangerous_actions,
            "text": text,
            "lang": lang,
            "created_at": time.time(),
        }

    def clear(self):
        self.pending = None

    def expired(self) -> bool:
        return bool(self.pending and time.time() - self.pending["created_at"] > self.timeout)

    def is_confirm(self, text: str, lang: str) -> bool:
        normalized = (text or "").strip().lower()
        words = CONFIRM_WORDS.get(lang, CONFIRM_WORDS["ru"]) | CONFIRM_WORDS["en"]
        return normalized in words

    def is_cancel(self, text: str, lang: str) -> bool:
        normalized = (text or "").strip().lower()
        words = CANCEL_WORDS.get(lang, CANCEL_WORDS["ru"]) | CANCEL_WORDS["en"]
        return normalized in words

    def prompt(self, lang: str, actions: list[str] | None = None) -> str:
        action_text = ""
        if actions:
            action_text = ", ".join(actions[:3])
        if lang == "en":
            if action_text:
                return f"This command can affect the system: {action_text}. Say 'confirm' to run it."
            return "This command can affect the system. Say 'confirm' to run it."
        if action_text:
            return f"Эта команда может повлиять на систему: {action_text}. Скажите: подтверждаю."
        return "Эта команда может повлиять на систему. Скажите: подтверждаю."
