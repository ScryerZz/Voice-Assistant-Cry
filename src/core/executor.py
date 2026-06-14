from src.skills.ai_skill import AISkill
from .matcher import SmartMatcher
from .safety import ConfirmationManager

class Executor:
    def __init__(self, dataset: dict, skill_manager, config: dict = None):
        self.config = config or {}
        self.dataset = dataset or {}
        self.skill_manager = skill_manager
        self.confirmations = ConfirmationManager(self.config)
        self.last_trace = self._empty_trace()
        self._init_matcher()

    def _init_matcher(self):
        matcher_config = self.config.get("matcher", {}) or {}
        self.matcher = SmartMatcher(
            self.dataset,
            threshold=matcher_config.get("threshold", self.config.get("matcher_threshold", 68)),
            debug=self.config.get("debug", False),
            config=self.config
        )

    def update_dataset(self, new_dataset: dict):
        self.dataset = new_dataset or {}
        self._init_matcher()

    def analyze(self, text: str, lang: str = "ru") -> dict:
        matches = self.matcher.find_matches(text)
        trace = self._trace_for_matches(matches)
        dangerous_matches = [
            match for match in matches
            if self.confirmations.requires_confirmation(match.get("action"))
        ]
        low_confidence_dangerous = [
            match for match in dangerous_matches
            if not self.confirmations.has_required_confidence(match)
        ]
        dangerous_actions = [
            str(match.get("action"))
            for match in dangerous_matches
            if match.get("action")
        ]
        if not matches:
            status = "no_match"
        elif low_confidence_dangerous:
            status = "dangerous_low_confidence"
        elif dangerous_matches:
            status = "confirmation_required"
        else:
            status = "matched"

        return {
            **trace,
            "status": status,
            "text": text,
            "lang": lang,
            "matches": matches,
            "dangerous_matches": dangerous_matches,
            "low_confidence_dangerous": low_confidence_dangerous,
            "dangerous_actions": dangerous_actions,
        }

    def handle(self, text: str, lang: str = "ru") -> str:
        self.last_trace = self._empty_trace()
        if self.confirmations.pending:
            if self.confirmations.expired():
                self.confirmations.clear()
                self.last_trace["status"] = "confirmation_timeout"
                return {
                    "ru": "Время подтверждения истекло. Команда отменена.",
                    "en": "Confirmation timed out. Command canceled.",
                }.get(lang, "Команда отменена.")

            if self.confirmations.is_cancel(text, lang):
                self.confirmations.clear()
                self.last_trace["status"] = "confirmation_cancelled"
                return {"ru": "Команда отменена.", "en": "Command canceled."}.get(lang, "Команда отменена.")

            if self.confirmations.is_confirm(text, lang):
                pending = self.confirmations.pending
                self.confirmations.clear()
                self._trace_matches(pending.get("matches", [pending["match"]]))
                self.last_trace["status"] = "confirmed"
                return self._execute_matches(pending.get("matches", [pending["match"]]), pending["text"], pending["lang"])

            self.confirmations.clear()
            self.last_trace["status"] = "confirmation_rejected"
            return {
                "ru": "Команда отменена. Для опасных действий нужна точная фраза: подтверждаю.",
                "en": "Command canceled. Dangerous actions require the exact phrase: confirm.",
            }.get(lang, "Команда отменена.")

        analysis = self.analyze(text, lang)
        matches = analysis["matches"]
        self.last_trace.update({
            "status": analysis["status"],
            "actions": list(analysis["actions"]),
            "patterns": list(analysis["patterns"]),
            "scores": list(analysis["scores"]),
        })

        if not matches:
            # AI (YandexGPT)
            ai_conf = self.config.get("assistant", {})
            if ai_conf.get("ai_enabled") and ai_conf.get("yandexgpt_api_key") and ai_conf.get("yandex_folder_id"):
                ai = AISkill(
                    api_key=ai_conf["yandexgpt_api_key"],
                    folder_id=ai_conf["yandex_folder_id"],
                    enabled=True,
                    debug=self.config.get("debug", False)
                )
                self.last_trace["status"] = "ai_fallback"
                return ai.ask(text, lang)

            self.last_trace["status"] = "no_match"
            return {
                "ru": "Извини, я не понял, что ты сказал.",
                "en": "Sorry, I did not understand."
            }.get(lang, "Извини, я не понял.")

        dangerous_matches = analysis["dangerous_matches"]
        if analysis["low_confidence_dangerous"]:
            self.last_trace["status"] = "dangerous_low_confidence"
            return {
                "ru": "Опасная команда распознана недостаточно уверенно. Повторите её точнее.",
                "en": "The dangerous command was not recognized confidently enough. Please repeat it more clearly.",
            }.get(lang, "Повторите команду точнее.")

        if dangerous_matches:
            self.confirmations.set_pending(dangerous_matches[0], text, lang, matches=matches)
            self.last_trace["status"] = "confirmation_required"
            return self.confirmations.prompt(lang, analysis["dangerous_actions"])

        responses = [self._execute_match(match, text, lang) for match in matches]

        self.last_trace["status"] = "matched"
        return " ".join(filter(None, responses))

    def _execute_matches(self, matches: list[dict], text: str, lang: str) -> str:
        responses = [self._execute_match(match, text, lang) for match in matches]
        return " ".join(filter(None, responses))

    def _execute_match(self, match: dict, text: str, lang: str) -> str:
        category = match.get("category")
        action = match.get("action")
        resp_cfg = match.get("response", "")

        if category in ("meta", "smalltalk"):
            if isinstance(resp_cfg, dict):
                return resp_cfg.get(lang, resp_cfg.get("en", ""))
            return str(resp_cfg)

        result = self.skill_manager.execute(action, text, lang=lang)
        if result and not str(result).startswith(("❌", "⚠️")):
            return str(result)

        if isinstance(resp_cfg, dict):
            return resp_cfg.get(lang, resp_cfg.get("en", ""))
        return str(resp_cfg or "")

    def _empty_trace(self) -> dict:
        return {
            "status": "unknown",
            "actions": [],
            "patterns": [],
            "scores": [],
        }

    def _trace_match(self, match: dict):
        action = match.get("action")
        pattern = match.get("pattern")
        score = match.get("score")
        if action:
            self.last_trace["actions"].append(str(action))
        if pattern:
            self.last_trace["patterns"].append(str(pattern))
        if score is not None:
            self.last_trace["scores"].append(str(score))

    def _trace_matches(self, matches: list[dict]):
        trace = self._trace_for_matches(matches)
        self.last_trace["actions"] = trace["actions"]
        self.last_trace["patterns"] = trace["patterns"]
        self.last_trace["scores"] = trace["scores"]

    def _trace_for_matches(self, matches: list[dict]) -> dict:
        trace = self._empty_trace()
        for match in matches:
            action = match.get("action")
            pattern = match.get("pattern")
            score = match.get("score")
            if action:
                trace["actions"].append(str(action))
            if pattern:
                trace["patterns"].append(str(pattern))
            if score is not None:
                trace["scores"].append(str(score))
        return trace
