# Архитектура

Voice Assistant Cry состоит из голосового runtime, desktop UI, набора навыков и локального хранилища.

## Основной Поток Голоса

```text
main.py
-> Settings
-> Recognizer
-> SmartMatcher
-> Executor
-> SkillManager
-> src/skills/*
-> TTS / SQLite / logs
```

1. `main.py` загружает настройки и dataset команд.
2. `Recognizer` слушает микрофон онлайн или офлайн.
3. Wake words очищаются из фразы.
4. `SmartMatcher` ищет подходящие команды.
5. `Executor` проверяет safety и подтверждения.
6. `SkillManager` вызывает функцию навыка.
7. Результат озвучивается, пишется в историю и логируется.

## Chat Runtime

Чат в `src/ui/config_app.py` использует тот же путь `Executor -> SmartMatcher -> SkillManager`, но без микрофона.

```text
текст в UI -> Executor -> SkillManager -> ответ в чат -> SQLite history
```

Если локальная команда не найдена и включён ЯндексGPT, `Executor` запускает `AISkill`.

## Ключевые Модули

| Модуль | Назначение |
| --- | --- |
| `src/core/config.py` | Дефолты, загрузка YAML, объединение user commands. |
| `src/core/recognizer.py` | SpeechRecognition, Vosk, восстановление аудиопотока. |
| `src/core/matcher.py` | Нормализация и fuzzy matching. |
| `src/core/executor.py` | Исполнение, safety, AI fallback. |
| `src/core/skill_manager.py` | Динамическая загрузка `src/skills/`. |
| `src/core/storage.py` | SQLite: заметки, напоминания, история. |
| `src/core/safety.py` | Подтверждение опасных команд. |
| `src/core/runtime_control.py` | Включение/отключение голосового считывания. |
| `src/core/support.py` | Профили, redaction, health/crash/support report. |
| `src/ui/config_app.py` | Tkinter UI. |

## UI

UI реализован на Tkinter. Главное окно, мастер первого запуска и живой журнал используют адаптивный стартовый размер, чтобы при открытии не требовать ручного растягивания.

Основные разделы:

- главная;
- чат;
- состояние;
- история;
- команды;
- заметки;
- напоминания;
- ассистент;
- профили;
- голос;
- интеграции;
- безопасность;
- приложения;
- диагностика;
- конфиг.

## Данные

| Данные | Файл |
| --- | --- |
| Настройки | `data/config.yaml` |
| Встроенные команды | `data/commands.yaml` |
| Пользовательские фразы | `data/user_commands.yaml` |
| SQLite | `data/assistant.sqlite3` |
| Runtime control | `data/runtime/control.json` |
| Журналы | `data/logs/` |
| Модели | `data/models/` |

Runtime-файлы не являются документацией и не должны удаляться без явного запроса.

## Safety

Опасные действия перечислены в `safety.dangerous_actions`. Для них `Executor` создаёт pending confirmation и ждёт точную фразу подтверждения.

Низкая уверенность для опасной команды не приводит к выполнению: ассистент просит повторить фразу точнее.

## Support

`src/core/support.py` формирует:

- health snapshot;
- crash summary;
- support-отчёт;
- профиль ассистента;
- очищенную от секретов конфигурацию.

API-ключи скрываются по умолчанию. История команд попадает в support-отчёт только если пользователь включил это в настройках приватности.
