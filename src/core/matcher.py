from rapidfuzz import process, fuzz
from functools import lru_cache
import re

class SmartMatcher:
    """
    Улучшенный сопоставитель команд.
    Теперь поддерживает 3 категории верхнего уровня:
    - skills
    - meta
    - smalltalk
    """

    def __init__(self, dataset: dict, threshold: int = 60, debug: bool = False, config: dict = None):
        self.dataset = dataset or {}
        self.threshold = threshold
        self.debug = debug
        self.config = config or {}
        matcher_config = self.config.get("matcher", {}) or {}
        self.partial_threshold = int(matcher_config.get("partial_threshold", max(78, self.threshold)))
        self.smalltalk_threshold = int(matcher_config.get("smalltalk_threshold", max(35, self.threshold - 25)))
        self.min_partial_length = int(matcher_config.get("min_partial_length", 5))
        # Собираем wake-words из конфигурации (если есть)
        self.wake_words = set()
        try:
            ww = self.config.get("wake_words", {}) or {}
            if isinstance(ww, dict):
                for v in ww.values():
                    if isinstance(v, (list, tuple)):
                        self.wake_words.update([w.lower() for w in v])
                    elif isinstance(v, str):
                        self.wake_words.add(v.lower())
            elif isinstance(ww, (list, tuple)):
                self.wake_words.update([w.lower() for w in ww])
            single = self.config.get("wake_word")
            if single:
                self.wake_words.add(single.lower())
        except Exception:
            pass

        # паттерны будут содержать: (orig, normalized, category, key, action, response)
        self.patterns = self._build_patterns()
        self.exact_patterns = {
            pattern[1]: pattern
            for pattern in self.patterns
            if pattern[1]
        }

    def log(self, *args):
        if self.debug:
            print("[DEBUG matcher]", *args)

    def _build_patterns(self):
        patterns = []

        # === Skills ===
        skills = self.dataset.get("skills", {}) or {}
        for category, data in skills.items():
            for idx, cmd in enumerate(data.get("commands", [])):
                pats = cmd.get("patterns", [])
                if isinstance(pats, str):
                    pats = [pats]
                for p in pats:
                    norm = self._normalize(p)
                    patterns.append((p, norm, "skills", category, cmd.get("action"), cmd.get("response", "")))

        # === Meta ===
        meta = self.dataset.get("meta", {}) or {}
        for key, m in meta.items():
            for p in m.get("patterns", []):
                norm = self._normalize(p)
                patterns.append((p, norm, "meta", key, None, m.get("response", "")))

        # === Smalltalk ===
        smalltalk = self.dataset.get("smalltalk", {}) or {}
        commands = smalltalk.get("commands", [])
        for idx, cmd in enumerate(commands):
            pats = cmd.get("patterns", [])
            if isinstance(pats, dict):
                all_pats = []
                for v in pats.values():
                    if isinstance(v, list):
                        all_pats.extend(v)
                    else:
                        all_pats.append(v)
            else:
                all_pats = pats or []
            for p in all_pats:
                norm = self._normalize(p)
                patterns.append((p, norm, "smalltalk", f"smalltalk_{idx}", None, cmd.get("response", "")))

        self.log(f"Loaded {len(patterns)} patterns total.")
        return patterns

    def _normalize(self, text: str) -> str:
        if not text:
            return ""

        # нормализация базовая
        text = str(text).replace("ё", "е").lower()
        text = re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)
        text = re.sub(r"\b(cry|край|к рай|краю|крае)\b", " ", text, flags=re.UNICODE)

        # удаляем wake-words в разных позициях
        if self.wake_words:
            for w in sorted(self.wake_words, key=len, reverse=True):
                # удаляем как отдельное слово
                text = re.sub(rf"\b{re.escape(w)}\b", " ", text)

        # расширенные стоп-слова на двух языках
        stopwords = {
            "ru": [
                "пожалуйста", "пжлст", "скажи", "скажи мне", "потом", "и", "еще",
                "пожалуйстa", "но", "так", "вообще", "иногда", "хорошо", "давай",
                "да", "ну", "мне", "ты", "можешь", "можно", "сейчас", "ладно",
            ],
            "en": ["please", "and", "then", "say", "tell", "now", "hey", "ok", "can", "you"]
        }
        sw = set()
        for v in stopwords.values():
            sw.update(v)

        tokens = [t for t in text.split() if t and t not in sw]
        return " ".join(tokens).strip()

    def _result_from_entry(self, entry, score: float) -> dict:
        return {
            "pattern": entry[0],
            "normalized_pattern": entry[1],
            "category": entry[2],
            "key": entry[3],
            "action": entry[4],
            "response": entry[5],
            "score": round(float(score), 2),
        }

    def _fuzzy_candidate_entries(self, normalized: str):
        normalized_word_count = len(normalized.split())
        if normalized_word_count <= 1:
            return self.patterns
        # Single-word commands are useful as exact commands, but they are risky
        # fuzzy candidates because token_set_ratio can over-match long phrases.
        return [
            entry for entry in self.patterns
            if len(str(entry[1]).split()) > 1
        ]

    @lru_cache(maxsize=2048)
    def _best_for_phrase(self, phrase: str):
        if not phrase:
            return None

        normalized = self._normalize(phrase)
        if not normalized:
            return None

        exact = self.exact_patterns.get(normalized)
        if exact:
            return self._result_from_entry(exact, 100)

        candidate_entries = self._fuzzy_candidate_entries(normalized)
        # choices — нормализованные паттерны
        choices = [p[1] for p in candidate_entries]
        if not choices:
            return None

        # 1) основной проход — token_set_ratio
        best_a = process.extractOne(normalized, choices, scorer=fuzz.token_set_ratio)
        # 2) token_sort_ratio полезен для переставленных слов
        best_sort = process.extractOne(normalized, choices, scorer=fuzz.token_sort_ratio)
        # 3) частичный проход — partial_ratio (лучше для длинных/фрагментированных фраз)
        best_b = process.extractOne(normalized, choices, scorer=fuzz.partial_ratio)

        candidates = [b for b in (best_a, best_sort) if b]
        if not candidates:
            return None

        best = max(candidates, key=lambda x: x[1])  # (match, score, idx)
        score = best[1]
        idx = best[2]
        pattern_entry = candidate_entries[idx]
        category = pattern_entry[2]

        # если хороший score >= порога — принимаем
        if score >= self.threshold:
            return self._result_from_entry(pattern_entry, score)

        # fallback 1: для smalltalk допускаем низкий порог (короткие/эмоциональные фразы)
        if category == "smalltalk" and score >= self.smalltalk_threshold:
            return self._result_from_entry(pattern_entry, score)

        # fallback 2: пытаемся ещё раз с более мягким порогом и partial scorer
        if best_b and best_b[1] >= self.partial_threshold and len(normalized.split()) >= self.min_partial_length:
            fb_idx = best_b[2]
            fb_entry = candidate_entries[fb_idx]
            return self._result_from_entry(fb_entry, best_b[1])

        # нет подходящего кандидата
        self.log(f"No good match for '{phrase}' (best={score})")
        return None

    def split_phrases(self, text: str):
        if not text:
            return []
        t = text.lower()
        # common separators in RU/EN to split multiple commands
        for sep in [" а потом ", " затем ", " потом ", " потом же ", " затем же ", " после этого ", " then ", " and then "]:
            t = t.replace(sep, " | ")
        return [p.strip() for p in t.split("|") if p.strip()]

    def find_matches(self, text: str):
        matches = []
        if not text:
            return matches
        for part in self.split_phrases(text):
            best = self._best_for_phrase(part)
            if best:
                matches.append(best)
        return matches
