from datetime import datetime


# === 🔢 Числа прописью ===
def number_to_words_ru(num: int) -> str:
    ones = [
        "ноль", "один", "два", "три", "четыре", "пять",
        "шесть", "семь", "восемь", "девять"
    ]
    teens = [
        "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
        "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"
    ]
    tens = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят"]

    if num < 10:
        return ones[num]
    elif num < 20:
        return teens[num - 10]
    elif num < 60:
        ten, one = divmod(num, 10)
        return f"{tens[ten]} {ones[one]}".strip()
    return str(num)


def number_to_words_en(num: int) -> str:
    ones = [
        "zero", "one", "two", "three", "four", "five",
        "six", "seven", "eight", "nine"
    ]
    teens = [
        "ten", "eleven", "twelve", "thirteen", "fourteen",
        "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"
    ]
    tens = ["", "", "twenty", "thirty", "forty", "fifty"]

    if num < 10:
        return ones[num]
    elif num < 20:
        return teens[num - 10]
    elif num < 60:
        ten, one = divmod(num, 10)
        return f"{tens[ten]} {ones[one]}".strip()
    return str(num)




# === 📅 Месяцы и годы ===
MONTHS = {
    "ru": {
        "January": "января", "February": "февраля", "March": "марта",
        "April": "апреля", "May": "мая", "June": "июня",
        "July": "июля", "August": "августа", "September": "сентября",
        "October": "октября", "November": "ноября", "December": "декабря"
    },
    "en": {
        "January": "January", "February": "February", "March": "March",
        "April": "April", "May": "May", "June": "June",
        "July": "July", "August": "August", "September": "September",
        "October": "October", "November": "November", "December": "December"
    },
}


# === 🗓️ Год прописью ===
def year_to_words_ru(year: int) -> str:
    thousands = {
        1000: "одна тысяча",
        2000: "две тысячи"
    }
    if year < 2000:
        return f"{thousands.get(1000)} {number_to_words_ru(year - 1000)}"
    elif 2000 <= year < 2100:
        remainder = year - 2000
        if remainder == 0:
            return "две тысячи"
        return f"две тысячи {number_to_words_ru(remainder)}"
    return str(year)


def year_to_words_en(year: int) -> str:
    if 2000 <= year < 2100:
        remainder = year - 2000
        if remainder == 0:
            return "two thousand"
        elif remainder < 10:
            return f"two thousand and {number_to_words_en(remainder)}"
        else:
            return f"two thousand {number_to_words_en(remainder)}"
    return str(year)




# === 🕒 Время ===
def get_time(*args, **kwargs):
    lang = kwargs.get("lang", "ru").lower()
    now = datetime.now()
    hour, minute = now.hour, now.minute

    if lang == "ru":
        return f"Сейчас {number_to_words_ru(hour)} {get_hour_word_ru(hour)}, {number_to_words_ru(minute)} {get_minute_word_ru(minute)}."
    elif lang == "en":
        return f"The time is {number_to_words_en(hour)} {get_hour_word_en(hour)} and {number_to_words_en(minute)} {get_minute_word_en(minute)}."
    else:
        return f"{hour:02d}:{minute:02d}"


# === 📅 Полная дата ===
def get_date(*args, **kwargs):
    lang = kwargs.get("lang", "ru").lower()
    now = datetime.now()
    day, year = now.day, now.year
    month_en = now.strftime("%B")

    if lang == "ru":
        return f"Сегодня {number_to_words_ru(day)} {MONTHS['ru'][month_en]} {year_to_words_ru(year)} года."
    elif lang == "en":
        return f"Today is {MONTHS['en'][month_en]} {number_to_words_en(day)}, {year_to_words_en(year)}."
    else:
        return now.strftime("%Y-%m-%d")


# === 🗣️ Склонения и формы ===
def get_hour_word_ru(hour: int) -> str:
    if hour % 10 == 1 and hour != 11:
        return "час"
    elif 2 <= hour % 10 <= 4 and not 12 <= hour <= 14:
        return "часа"
    return "часов"


def get_minute_word_ru(minute: int) -> str:
    if minute % 10 == 1 and minute != 11:
        return "минута"
    elif 2 <= minute % 10 <= 4 and not 12 <= minute <= 14:
        return "минуты"
    return "минут"


def get_hour_word_en(hour: int) -> str:
    return "hour" if hour == 1 else "hours"


def get_minute_word_en(minute: int) -> str:
    return "minute" if minute == 1 else "minutes"


