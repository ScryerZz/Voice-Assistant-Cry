# AI-Агенты Разработки

Этот документ описывает постоянные роли из `.agents/`. Это роли для разработки, а не функции голосового ассистента.

## Роли

| Роль | Фокус | Основные файлы |
| --- | --- | --- |
| Product Lead | Ценность, roadmap, релизный объём | `docs/ROADMAP.md`, `docs/USER_GUIDE.md` |
| UX/UI Designer | UI, onboarding, доступность | `src/ui/config_app.py`, `ui.py` |
| Runtime Engineer | Микрофон, Vosk, TTS, lifecycle | `main.py`, `src/core/recognizer.py`, `src/core/tts.py` |
| Commands & Skills Engineer | Команды, matcher, навыки | `data/commands.yaml`, `src/skills/`, `src/core/matcher.py` |
| QA & Diagnostics Engineer | Тесты, диагностика, smoke checks | `diagnose.py`, `tests/` |
| Safety & Privacy Engineer | Опасные действия, секреты, данные | `src/core/safety.py`, `src/core/support.py`, `data/config.yaml` |
| Documentation & Support Engineer | Документация и support | `README.md`, `docs/`, `AGENTS.md` |
| Packaging & Release Engineer | Финальная упаковка | packaging scripts, release docs |

## Когда Использовать

- Product Lead: при изменении приоритетов и release scope.
- UX/UI Designer: при изменении экранов, размеров окон, мастера, чата, доступности.
- Runtime Engineer: при изменении микрофона, распознавания, TTS, потоков и остановки.
- Commands & Skills Engineer: при изменении команд, навыков, matcher.
- QA & Diagnostics Engineer: при тестах, `diagnose.py`, release readiness.
- Safety & Privacy Engineer: при секретах, логах, истории, dangerous actions.
- Documentation & Support Engineer: после любой пользовательской правки.
- Packaging & Release Engineer: только на финальном этапе `.exe`.

## Текущий Приоритет

| Этап | Роли |
| --- | --- |
| Предсборочная проверка | QA & Diagnostics, UX/UI, Documentation & Support |
| Packaging readiness | Product Lead, Packaging & Release |
| Финальная `.exe` сборка | Packaging & Release, QA & Diagnostics |

Packaging относится к P3 и не должен запускаться до явной команды пользователя.

См. [ROADMAP.md](ROADMAP.md).
