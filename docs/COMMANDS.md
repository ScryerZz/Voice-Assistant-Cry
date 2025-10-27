# ⚙️ Документация: как создавать и управлять командами в `commands.yaml`

---

## 🧩 Общая структура системы

Система команд ассистента построена на основе **трёх уровней логики**:

| Категория     | Назначение                                                 | Примеры                                         |
| ------------- | ---------------------------------------------------------- | ----------------------------------------------- |
| **skills**    | Основные функции ассистента (работа, поиск, музыка и т.д.) | `system.shutdown`, `search_web.search_internet` |
| **meta**      | Внутренние служебные операции                              | `reload_dataset`, `restart_skills`              |
| **smalltalk** | Простой разговорный режим                                  | “ты молодец”, “спасибо”, “how are you”          |

---

## 🧠 Как всё работает

1. Пользователь говорит фразу → текст распознаётся
2. **Executor** вызывает `SmartMatcher` → ищет совпадение по `patterns`
3. Если найдено совпадение:

   * Если категория = **skills** → вызывается функция из `src/skills/`
   * Если категория = **meta** → выполняется системное действие (например, перезапуск)
   * Если категория = **smalltalk** → возвращается готовый ответ
4. Если ничего не найдено → ассистент использует AI fallback (`GeminiSkill` или другой LLM)

---

## 📂 Структура `commands.yaml`

Файл `commands.yaml` делится на разделы, каждый из которых описывает группу команд:

```yaml
skills:
  system:
    description: "Системные команды"
    commands:
      - patterns:
          - "выключи компьютер"
          - "shutdown"
        action: system.shutdown
        response:
          ru: "Выключаю компьютер."
          en: "Shutting down."
```

Каждая команда содержит:

| Поле                           | Назначение                               |
| ------------------------------ | ---------------------------------------- |
| **patterns**                   | список возможных фраз (триггеров)        |
| **action**                     | путь к функции в `src/skills/`           |
| **response**                   | ответ, если функция не вернула результат |
| **category** *(необязательно)* | метка (`smalltalk`, `meta` и т.д.)       |

---

## 🧰 Пример полного `commands.yaml`

```yaml
skills:
  assistant_control:
    description: "Команды управления ассистентом"
    commands:
      - patterns:
          - "выключись"
          - "останови работу"
          - "terminate"
        action: assistant_control.shutdown_assistant
        response:
          ru: "Останавливаю работу, сэр."
          en: "Stopping assistant."

  system:
    description: "Системные команды"
    commands:
      - patterns:
          - "выключи компьютер"
          - "turn off pc"
        action: system.shutdown
        response:
          ru: "Выключаю компьютер."
          en: "Turning off the PC."

  search_web:
    description: "Интернет поиск"
    commands:
      - patterns:
          - "найди в интернете"
          - "search online"
        action: search_web.search_internet
        response:
          ru: "Ищу информацию в интернете..."
          en: "Searching the web..."

meta:
  reload_dataset:
    patterns:
      - "перезагрузи команды"
      - "reload dataset"
    response:
      ru: "Датасет обновлён."
      en: "Dataset reloaded."

  restart_skills:
    patterns:
      - "перезапусти навыки"
      - "reload skills"
    response:
      ru: "Навыки перезапущены."
      en: "Skills reloaded."

smalltalk:
  description: "Простые разговорные ответы"
  commands:
    - patterns:
        - "ты молодец"
        - "good job"
      category: "smalltalk"
      response:
        ru: "Спасибо, сэр. Вы тоже на высоте!"
        en: "Thank you, sir. You're amazing too!"

    - patterns:
        - "ты тупой"
        - "stupid"
      category: "smalltalk"
      response:
        ru: "Очень тонкое замечание, сэр."
        en: "A very subtle remark, sir."
```

---

## 🧩 Как создаются функции (`skills`)

Все функции навыков пишутся в `src/skills/`
и принимают сигнатуру:

```python
def some_function(*args, **kwargs):
    ...
```

Это делает их гибкими и универсальными.

### 📦 Что передаётся в `kwargs`

| Ключ            | Тип    | Описание                                       |
| --------------- | ------ | ---------------------------------------------- |
| `text`          | str    | исходная команда пользователя                  |
| `lang`          | str    | текущий язык ассистента (`ru`, `en`)     |
| `dataset`       | dict   | весь `commands.yaml`                           |
| `config`        | dict   | глобальные настройки из `config.yaml`          |
| `skill_manager` | объект | менеджер скиллов (можно вызвать другие)        |
| `workers`       | list   | список активных потоков ассистента             |
| `tts`           | объект | движок озвучивания (если нужно проговаривание) |

---

## 🧠 Пример универсальной функции

```python
# src/skills/search_web.py
import re
import webbrowser

def search_internet(*args, **kwargs):
    """
    Универсальная функция поиска в интернете.
    Работает с любыми аргументами (*args, **kwargs).
    """

    dataset = kwargs.get("dataset", {})
    query = kwargs.get("text")
    lang = kwargs.get("lang", "ru")

    if not query and args:
        query = " ".join(str(a) for a in args if isinstance(a, str)).strip()

    if not query:
        return {"ru": "⚠️ Не понял, что искать.", "en": "I didn’t understand what to search."}.get(lang)

    # Извлекаем паттерны
    patterns = []
    for cat, cat_data in dataset.get("skills", {}).items():
        for cmd in cat_data.get("commands", []):
            if cmd.get("action") == "search_web.search_internet":
                patterns.extend(cmd.get("patterns", []))

    clean_query = query.lower()
    for pattern in patterns:
        clean_query = re.sub(re.escape(pattern.lower()), "", clean_query, flags=re.IGNORECASE)

    clean_query = re.sub(r"\b(край|cry)[,]*", "", clean_query, flags=re.IGNORECASE)
    clean_query = clean_query.strip()

    if not clean_query:
        return "⚠️ Не понял, что искать."

    webbrowser.open(f"https://www.google.com/search?q={clean_query}")
    return f"🔎 Ищу в интернете: {clean_query}"
```

---

## 🪄 Пример: создать новую функцию

### 1. Создай файл `src/skills/example_skill.py`

```python
def say_hello(*args, **kwargs):
    text = kwargs.get("text", "")
    name = text.replace("поздоровайся с", "").strip()
    return f"Привет, {name}!" if name else "Привет, сэр!"
```

### 2. Добавь в `commands.yaml`

```yaml
skills:
  example:
    description: "Пример пользовательской функции"
    commands:
      - patterns:
          - "поздоровайся"
          - "скажи привет"
        action: example.say_hello
        response:
          ru: "Привет, сэр!"
```

---

## 🔧 Как работает `SkillManager`

```python
class SkillManager:
    def __init__(self, config, dataset):
        self.config = config
        self.dataset = dataset
        self.skills = self._load_skills()

    def _load_skills(self):
        # динамическая загрузка модулей из src/skills/
        ...

    def execute(self, action, text=None, *args, **kwargs):
        try:
            module_name, func_name = action.split(".")
            module = self.skills.get(module_name)
            func = getattr(module, func_name, None)
            if not func:
                return f"⚠️ Функция '{func_name}' не найдена."
            kwargs.update({
                "dataset": self.dataset,
                "config": self.config,
                "text": text
            })
            return func(*args, **kwargs)
        except Exception as e:
            return f"❌ Ошибка при выполнении: {e}"
```

---

## 🧭 Расширение функционала

Ты можешь:

* Добавлять свои **категории** в `commands.yaml` (например, `ai_tools`, `developer_tools`)
* Делать свои **meta-команды** для перезагрузки подсистем
* Добавлять **fallback AI-ответы** при отсутствии совпадений
* Делать команды с **условиями** (например, проверка времени суток)

---

## ⚡ Советы по оптимизации

| 💡 Советы                                                            | 🧾 Объяснение                                             |
| -------------------------------------------------------------------- | --------------------------------------------------------- |
| **Используй `*args, **kwargs`**                                      | не нужно менять сигнатуру при добавлении новых параметров |
| **Передавай `dataset` в kwargs**                                     | можно анализировать другие паттерны                       |
| **Используй “patterns” максимально разнообразно**                    | улучшает точность SmartMatcher                            |
| **Для сложных функций используй context (config, workers)**          | чтобы вызывать системные методы                           |
| **Отделяй smalltalk в отдельный блок**                               | чтобы не мешал логике команд                              |
| **В meta-командах не указывай action**, если не требуется выполнение | они могут просто отдавать `response`                      |

---

## 🎯 Пример добавления “умной” команды

```yaml
skills:
  time_info:
    description: "Команды для времени"
    commands:
      - patterns:
          - "который час"
          - "what time is it"
        action: time_info.tell_time
        response:
          ru: "Сейчас {time}."
          en: "It's {time} now."
```

```python
# src/skills/time_info.py
from datetime import datetime

def tell_time(*args, **kwargs):
    lang = kwargs.get("lang", "ru")
    now = datetime.now().strftime("%H:%M")
    responses = {
        "ru": f"Сейчас {now}.",
        "en": f"It's {now} now."
    }
    return responses.get(lang, responses["ru"])
```

---

## ✅ Резюме

| Компонент                       | Назначение                                             |
| ------------------------------- | ------------------------------------------------------ |
| **commands.yaml**               | хранит все команды, их паттерны и ответы               |
| **SmartMatcher**                | находит совпадения с командами                         |
| **Executor**                    | управляет логикой ответа (meta / skills / smalltalk)   |
| **SkillManager**                | вызывает соответствующую функцию                       |
| **Функции с `*args, **kwargs`** | гибкий способ писать навыки без ограничения параметров |

