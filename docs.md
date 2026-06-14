# Карта Документации

Это корневой индекс документации Voice Assistant Cry.

## Для Пользователя

- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) - установка, первый запуск, чат, голос, профили, интеграции.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - решение типовых проблем.
- [docs/SCREENSHOTS.md](docs/SCREENSHOTS.md) - список скриншотов для финальной документации и support.

## Для Разработки

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - как устроен runtime, UI, команды и support-инструменты.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - окружение, команды проверки, правила разработки.
- [docs/COMMANDS.md](docs/COMMANDS.md) - структура команд и навыков.
- [docs/CONFIG.md](docs/CONFIG.md) - схема конфигурации.
- [docs/PACKAGING.md](docs/PACKAGING.md) - состав `.exe`-сборки, runtime-данные, модели и секреты.
- [docs/ROADMAP.md](docs/ROADMAP.md) - план доведения до релиза.
- [docs/AI_AGENTS.md](docs/AI_AGENTS.md) - роли субагентов разработки.

## Для Coding Agents

- [AGENTS.md](AGENTS.md) - обязательные правила работы в репозитории.
- [.agents/README.md](.agents/README.md) - постоянные роли специалистов.

## Источники Правды

| Область | Файлы |
| --- | --- |
| Настройки | `data/config.yaml`, `src/core/config.py` |
| Команды | `data/commands.yaml`, `data/user_commands.yaml` |
| Голосовой runtime | `main.py`, `src/core/recognizer.py`, `src/core/tts.py` |
| Исполнение команд | `src/core/matcher.py`, `src/core/executor.py`, `src/core/skill_manager.py` |
| UI | `ui.py`, `src/ui/config_app.py` |
| Хранилище | `src/core/storage.py` |
| Безопасность | `src/core/safety.py` |
| Диагностика | `diagnose.py`, `src/core/support.py` |

## Правила Поддержки Документации

- `README.md` держим коротким.
- Подробности храним в `docs/`.
- Исторические логи не переносим в Markdown.
- Сборку `.exe` не описываем как готовую, пока она реально не выполнена.
