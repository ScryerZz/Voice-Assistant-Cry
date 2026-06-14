# Разработка

Документ описывает текущий рабочий процесс разработки Voice Assistant Cry.

## Окружение

Целевой runtime:

```text
Windows
Python 3.11
```

Установка:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Запуск

UI:

```powershell
.\.venv\Scripts\python.exe ui.py
```

Голосовой runtime:

```powershell
.\.venv\Scripts\python.exe main.py
```

Диагностика:

```powershell
.\.venv\Scripts\python.exe diagnose.py
```

Windows-скрипты:

```bat
install.bat
run_settings.bat
run_assistant.bat
run_diagnostics.bat
```

## Обязательные Проверки

Перед предрелизным этапом:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe diagnose.py
.\.venv\Scripts\python.exe -m compileall main.py ui.py diagnose.py src tests
```

`diagnose.py` проверяет зависимости, микрофонные устройства, YAML, команды, matcher, chat executor, UI lifecycle, imports, SQLite, runtime control, журналы и секреты в логах.

## Изменение UI

Основной файл:

```text
src/ui/config_app.py
```

После UI-правок:

```powershell
.\.venv\Scripts\python.exe -m compileall ui.py src\ui\config_app.py
.\.venv\Scripts\python.exe diagnose.py
```

Если менялись размеры или layout, нужно открыть `run_settings.bat` и визуально проверить главное окно, мастер первого запуска и живой журнал.

## Добавление Навыка

1. Создайте модуль в `src/skills/`.
2. Функции должны принимать `*args, **kwargs`.
3. Добавьте action в `data/commands.yaml`.
4. Для опасных действий обновите `safety.dangerous_actions`.
5. Добавьте тест, если есть логика.
6. Обновите `docs/COMMANDS.md`.
7. Запустите проверки.

## Изменение Конфига

1. Добавьте дефолт в `src/core/config.py`.
2. Добавьте UI-контрол, если настройка пользовательская.
3. Обновите `docs/CONFIG.md`.
4. Проверьте `diagnose.py`.

## Runtime-Данные

Не считать исходниками:

```text
data/assistant.sqlite3
data/logs/
data/runtime/
data/cache/
data/models/
```

Не удалять без явного запроса пользователя.

## Документация

При изменениях обновлять:

- `README.md` и `docs/USER_GUIDE.md` при изменении запуска;
- `docs/CONFIG.md` при изменении настроек;
- `docs/COMMANDS.md` при изменении команд;
- `docs/ARCHITECTURE.md` при изменении runtime/UI;
- `docs/TROUBLESHOOTING.md` при новых типовых ошибках;
- `docs/ROADMAP.md` при изменении плана;
- `AGENTS.md` при изменении правил работы агентов.

## Packaging

Финальную сборку `.exe` не выполнять до явного запроса пользователя. Перед ней обязательно прогнать полный набор проверок и визуально проверить UI.
