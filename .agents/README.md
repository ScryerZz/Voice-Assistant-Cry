# Роли AI-Агентов

Эта папка хранит постоянные роли для будущих проходов разработки. Они не загружаются голосовым ассистентом и не являются runtime-кодом.

## Список Ролей

| Роль | Файл | Ответственность |
| --- | --- | --- |
| Product Lead | `product-lead.md` | Ценность, roadmap, приоритеты, release scope. |
| UX/UI Designer | `ux-ui-designer.md` | Desktop UI, onboarding, доступность, пользовательские потоки. |
| Runtime Engineer | `runtime-engineer.md` | Голосовой цикл, recognizer, TTS, потоки, lifecycle. |
| Commands & Skills Engineer | `commands-skills-engineer.md` | `data/commands.yaml`, `src/skills/`, intents, actions. |
| QA & Diagnostics Engineer | `qa-diagnostics-engineer.md` | Тесты, `diagnose.py`, smoke checks, regression coverage. |
| Safety & Privacy Engineer | `safety-privacy-engineer.md` | Опасные действия, подтверждения, данные, секреты. |
| Documentation & Support Engineer | `docs-support-engineer.md` | Документация, troubleshooting, support flow. |
| Packaging & Release Engineer | `packaging-release-engineer.md` | Финальная `.exe` сборка, installer, release readiness. |

## Как Использовать

1. Сначала прочитать `AGENTS.md`.
2. Выбрать роль по зоне ответственности.
3. Работать в пределах роли, если задача не требует координации.
4. Не откатывать чужие изменения.
5. После изменений запускать проверки из роли.
6. При изменении scope обновлять `docs/ROADMAP.md`.
