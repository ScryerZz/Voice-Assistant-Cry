# Команды И Навыки

Встроенные команды находятся в:

```text
data/commands.yaml
```

Пользовательские фразы, добавленные из UI, сохраняются отдельно:

```text
data/user_commands.yaml
```

При запуске `Settings` объединяет оба файла. Поэтому пользовательские фразы работают и в чате, и в голосовом режиме.

## Как Выполняется Команда

```text
фраза пользователя
-> очистка wake words и мусорных слов
-> SmartMatcher
-> Executor
-> проверка safety
-> SkillManager
-> функция в src/skills/
-> ответ + история
```

## Структура YAML

```yaml
skills:
  rutube:
    description: Поиск на Rutube
    commands:
      - patterns:
          - найди на рутубе
        action: rutube.search_rutube
        response:
          ru: Ищу на Rutube...
```

`action` состоит из:

```text
модуль.функция
```

Пример:

```text
rutube.search_rutube -> src/skills/rutube.py -> search_rutube()
```

## Основные Разделы Навыков

| Раздел | Назначение |
| --- | --- |
| `assistant_control` | Завершение ассистента, язык. |
| `assistant_info` | Справка, примеры, диагностика. |
| `logs` | Журнал событий. |
| `history` | История команд. |
| `system` | Браузер и системные действия. |
| `time_date` | Время и дата. |
| `music` | Локальная музыка. |
| `weather` | Погода. |
| `news` | Новости. |
| `notes` | Заметки. |
| `reminders` | Таймеры и напоминания. |
| `rutube` | Поиск видео на Rutube. |
| `translator` | Перевод текста. |
| `system_info` | Система и батарея. |
| `system_control` | Скриншоты, громкость, очистка. |
| `apps` | Открытие, закрытие и статус приложений. |

Старые фразы про YouTube оставлены как алиасы, но открывают Rutube.

## Пользовательские Фразы

Обычный пользователь добавляет фразы через UI:

```text
Команды -> выбрать команду -> Добавить фразу
```

UI сохраняет их в `data/user_commands.yaml`. Встроенный `data/commands.yaml` при этом не меняется.

## Опасные Команды

Если действие влияет на систему или удаляет данные, добавьте его в:

```yaml
safety:
  dangerous_actions:
    - system.shutdown
    - system.restart
```

Пользователь может включать/выключать подтверждение из вкладки `Команды`. Для выключения и перезагрузки ассистент сначала просит точную фразу `подтверждаю`, затем планирует действие с задержкой. Команда `отмени выключение` или `отмени перезагрузку` отменяет запланированное действие Windows.

## Хорошие Patterns

- Короткие и естественные.
- Без слишком общих однословных фраз, если действие опасное.
- Отдельный intent - отдельное action.
- Русские варианты важнее английских для текущей аудитории.
- Для команд с аргументом нужна понятная ошибка, если аргумент не указан.

## Первые Команды Для Проверки

| Фраза | Action |
| --- | --- |
| `что ты умеешь` | `assistant_info.list_capabilities` |
| `примеры команд` | `assistant_info.show_example_commands` |
| `проверь ассистента` | `assistant_info.run_diagnostics` |
| `последние команды` | `history.recent_history` |
| `где журнал` | `logs.log_status` |
| `открой браузер` | `system.open_browser` |
| `отмени выключение` | `system.cancel_shutdown` |
| `найди на рутубе музыка` | `rutube.search_rutube` |
| `какая погода` | `weather.get_weather` |
| `последние новости` | `news.search_news` |
| `поставь таймер на пять минут` | `reminder.set_timer` |

## Как Добавить Навык

1. Создайте модуль в `src/skills/`.
2. Добавьте функцию с `*args, **kwargs`.
3. Добавьте action в `data/commands.yaml`.
4. Если действие опасное, добавьте его в `safety.dangerous_actions`.
5. Добавьте тест, если поведение нетривиальное.
6. Запустите:

```powershell
.\.venv\Scripts\python.exe diagnose.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```
