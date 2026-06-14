import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.core.storage import AssistantStorage


@dataclass(frozen=True)
class ParsedReminderTime:
    due_at: datetime | None
    text: str
    matched_text: str | None = None
    delay_seconds: int | None = None


_HALF_HOUR_RE = re.compile(r"\bчерез\s+пол\s*часа\b", re.IGNORECASE)
_RU_RELATIVE_RE = re.compile(
    r"\bчерез\s+(?P<amount>\d+)\s*"
    r"(?P<unit>минуту|минуты|минут|мин|часов|часа|час|ч)\b",
    re.IGNORECASE,
)
_EN_RELATIVE_RE = re.compile(
    r"\bin\s+(?P<amount>\d+)\s*(?P<unit>minutes?|mins?|hours?|hrs?)\b",
    re.IGNORECASE,
)
_RU_ABSOLUTE_RE = re.compile(
    r"\b(?P<day>сегодня|завтра)\s+в\s+"
    r"(?P<hour>[01]?\d|2[0-3])[:.](?P<minute>[0-5]\d)\b",
    re.IGNORECASE,
)
_EN_ABSOLUTE_RE = re.compile(
    r"\b(?P<day>today|tomorrow)\s+at\s+"
    r"(?P<hour>[01]?\d|2[0-3])[:.](?P<minute>[0-5]\d)\b",
    re.IGNORECASE,
)
_RU_BARE_TIME_RE = re.compile(
    r"(?<!\S)в\s+(?P<hour>[01]?\d|2[0-3])[:.](?P<minute>[0-5]\d)\b",
    re.IGNORECASE,
)
_EN_BARE_TIME_RE = re.compile(
    r"\bat\s+(?P<hour>[01]?\d|2[0-3])[:.](?P<minute>[0-5]\d)\b",
    re.IGNORECASE,
)
_REMINDER_PREFIX_RE = re.compile(
    r"^\s*(?:напомни(?:\s+мне)?|напоминание|remind(?:\s+me)?|reminder)\b[\s:,-]*",
    re.IGNORECASE,
)
_EN_LEADING_TO_RE = re.compile(r"^\s*to\s+", re.IGNORECASE)


def parse_reminder_time(text: str, now: datetime | None = None) -> ParsedReminderTime:
    """
    Parses a reminder time phrase and returns due_at plus text without the time phrase.
    The function has no storage side effects; pass now in tests for deterministic results.
    """
    now = now or datetime.now()
    source = (text or "").strip()
    if not source:
        return ParsedReminderTime(due_at=None, text="")

    match = _HALF_HOUR_RE.search(source)
    if match:
        delay_seconds = 30 * 60
        return ParsedReminderTime(
            due_at=now + timedelta(seconds=delay_seconds),
            text=_without_match(source, match),
            matched_text=match.group(0),
            delay_seconds=delay_seconds,
        )

    match = _RU_RELATIVE_RE.search(source)
    if match:
        delay_seconds = _relative_seconds(int(match.group("amount")), match.group("unit"))
        return ParsedReminderTime(
            due_at=now + timedelta(seconds=delay_seconds),
            text=_without_match(source, match),
            matched_text=match.group(0),
            delay_seconds=delay_seconds,
        )

    match = _EN_RELATIVE_RE.search(source)
    if match:
        delay_seconds = _relative_seconds(int(match.group("amount")), match.group("unit"))
        return ParsedReminderTime(
            due_at=now + timedelta(seconds=delay_seconds),
            text=_without_match(source, match),
            matched_text=match.group(0),
            delay_seconds=delay_seconds,
        )

    match = _RU_ABSOLUTE_RE.search(source)
    if match:
        return _absolute_result(source, match, now, match.group("day"), roll_forward=False)

    match = _EN_ABSOLUTE_RE.search(source)
    if match:
        return _absolute_result(source, match, now, match.group("day"), roll_forward=False)

    match = _RU_BARE_TIME_RE.search(source)
    if match:
        return _absolute_result(source, match, now, day=None, roll_forward=True)

    match = _EN_BARE_TIME_RE.search(source)
    if match:
        return _absolute_result(source, match, now, day=None, roll_forward=True)

    return ParsedReminderTime(due_at=None, text=source)


def set_timer(*args, **kwargs):
    """
    Устанавливает таймер на указанное количество секунд/минут.
    Примеры: "поставь таймер на 5 минут", "таймер на 30 секунд"
    """
    text = kwargs.get("text", "") or " ".join(str(a) for a in args if isinstance(a, str))
    text = text.strip().lower()
    
    if not text:
        return "⚠️ Не понял, на сколько установить таймер."
    
    # Извлекаем время
    seconds = 0
    
    # Поиск минут
    min_match = re.search(r"(\d+)\s*(минут|минуты|минуту|minute|minutes)", text)
    if min_match:
        seconds += int(min_match.group(1)) * 60
    
    # Поиск секунд
    sec_match = re.search(r"(\d+)\s*(секунд|секунды|секунду|second|seconds)", text)
    if sec_match:
        seconds += int(sec_match.group(1))
    
    # Если не нашли конкретное время, пробуем просто число
    if seconds == 0:
        num_match = re.search(r"(\d+)", text)
        if num_match:
            seconds = int(num_match.group(1)) * 60  # по умолчанию минуты
    
    if seconds == 0:
        return "⚠️ Не понял, на сколько времени установить таймер."
    
    due_at = datetime.now() + timedelta(seconds=seconds)
    storage = _storage(kwargs)
    storage.add_reminder("timer", "время вышло", due_at)
    
    if seconds >= 60:
        minutes = seconds // 60
        return f"⏰ Таймер установлен на {minutes} минут."
    return f"⏰ Таймер установлен на {seconds} секунд."


def set_reminder(*args, **kwargs):
    """
    Устанавливает напоминание с текстом и задержкой.
    Примеры: "напомни через 5 минут купить молоко", "напомни через час позвонить"
    """
    text = kwargs.get("text", "") or " ".join(str(a) for a in args if isinstance(a, str))
    text = text.strip()
    
    if not text:
        return "⚠️ Не понял, о чём напомнить."
    
    now = kwargs.get("now") or datetime.now()
    parsed = parse_reminder_time(text, now=now)
    delay_seconds = parsed.delay_seconds
    due_at = parsed.due_at

    if due_at is None:
        delay_seconds = 300
        due_at = now + timedelta(seconds=delay_seconds)

    clean_text = _clean_reminder_text(parsed.text)
    if not clean_text:
        clean_text = "время вышло"

    storage = _storage(kwargs)
    storage.add_reminder("reminder", clean_text, due_at)

    return f"🔔 Напоминание установлено {_format_due(due_at, delay_seconds)}: {clean_text}"


def _absolute_result(source: str, match: re.Match, now: datetime, day: str | None, roll_forward: bool) -> ParsedReminderTime:
    due_at = _absolute_due_at(
        now,
        int(match.group("hour")),
        int(match.group("minute")),
        day=day,
        roll_forward=roll_forward,
    )
    return ParsedReminderTime(
        due_at=due_at,
        text=_without_match(source, match),
        matched_text=match.group(0),
        delay_seconds=None,
    )


def _absolute_due_at(now: datetime, hour: int, minute: int, day: str | None, roll_forward: bool) -> datetime:
    day_key = (day or "").lower()
    base = now + timedelta(days=1) if day_key in {"завтра", "tomorrow"} else now
    due_at = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if roll_forward and due_at <= now:
        due_at += timedelta(days=1)
    return due_at


def _relative_seconds(amount: int, unit: str) -> int:
    unit_key = unit.lower()
    if unit_key in {"час", "часа", "часов", "ч", "hour", "hours", "hr", "hrs"}:
        return amount * 3600
    return amount * 60


def _without_match(text: str, match: re.Match) -> str:
    return _normalize_spaces(f"{text[:match.start()]} {text[match.end():]}")


def _clean_reminder_text(text: str) -> str:
    clean_text = _REMINDER_PREFIX_RE.sub("", text)
    clean_text = _EN_LEADING_TO_RE.sub("", clean_text)
    return _normalize_spaces(clean_text)


def _normalize_spaces(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text)
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    normalized = re.sub(r"([,.;:!?]){2,}", r"\1", normalized)
    return normalized.strip(" \t\r\n,.;:-")


def _format_due(due_at: datetime, delay_seconds: int | None) -> str:
    if delay_seconds is None:
        return f"на {due_at.strftime('%Y-%m-%d %H:%M')}"
    if delay_seconds >= 3600:
        hours = delay_seconds // 3600
        return f"на {hours} час(а)"
    if delay_seconds >= 60:
        minutes = delay_seconds // 60
        return f"на {minutes} минут"
    return f"на {delay_seconds} секунд"


def _storage(kwargs) -> AssistantStorage:
    storage = kwargs.get("storage")
    if storage:
        return storage
    config = kwargs.get("config", {}) or {}
    db_path = config.get("paths", {}).get("database")
    return AssistantStorage(db_path)
