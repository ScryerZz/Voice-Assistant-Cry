# Agent Instructions

These instructions are for coding agents working in this repository.

## Repository Context

Voice Assistant Cry is a Windows-first Python voice assistant. The current safe runtime target is Python 3.11.

Important entry points:

- `main.py` starts the voice assistant.
- `ui.py` starts the desktop UI.
- `diagnose.py` runs project checks without starting the microphone.
- `data/config.yaml` stores user settings.
- `data/commands.yaml` stores command patterns and actions.
- `.agents/` stores persistent specialist development roles.
- `docs/ROADMAP.md` stores the product plan.

## Work Rules

- Do not build the final `.exe` unless the user explicitly asks for that final stage.
- Do not delete or reset user/runtime data unless explicitly requested.
- Do not revert unrelated dirty files.
- Keep `README.md` short and move technical detail to `docs/`.
- Keep historical logs out of Markdown; use Git history for historical detail.
- Prefer the existing architecture: `Recognizer`, `SmartMatcher`, `Executor`, `SkillManager`, `AssistantStorage`, Tkinter UI.
- New skills should live in `src/skills/` and accept `*args, **kwargs`.
- New command actions must be added to `data/commands.yaml`.
- Destructive/system-affecting actions must be added to `safety.dangerous_actions` in `data/config.yaml`.

## Runtime Files

These are generated state, not source documentation:

- `data/assistant.sqlite3`
- `data/logs/`
- `data/runtime/`
- `data/cache/`
- Vosk/Silero model folders under `data/models/`

Do not treat those files as documentation inputs except when debugging a concrete issue.

## Recommended Commands

Set up:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Check:

```powershell
.\.venv\Scripts\python.exe diagnose.py
.\.venv\Scripts\python.exe -m compileall main.py ui.py diagnose.py src
```

Run UI:

```powershell
.\.venv\Scripts\python.exe ui.py
```

Run assistant:

```powershell
.\.venv\Scripts\python.exe main.py
```

## Documentation Checklist

When changing:

- startup or installation, update `README.md`, `docs/USER_GUIDE.md`, and `docs/DEVELOPMENT.md`;
- config schema/defaults, update `docs/CONFIG.md`;
- command schema/matcher/skills, update `docs/COMMANDS.md`;
- runtime architecture, update `docs/ARCHITECTURE.md`;
- common failures, update `docs/TROUBLESHOOTING.md`;
- roadmap scope/priorities, update `docs/ROADMAP.md`;
- specialist role ownership, update `.agents/` and `docs/AI_AGENTS.md`;
- repository workflow, update this file.

## Specialist Roles

Use `.agents/README.md` and `docs/AI_AGENTS.md` to choose a focused role:

- Product Lead for roadmap and release scope.
- UX/UI Designer for user flows and desktop UI.
- Runtime Engineer for recognition, TTS, workers, and lifecycle.
- Commands & Skills Engineer for command matching and skills.
- QA & Diagnostics Engineer for tests and diagnostics.
- Safety & Privacy Engineer for confirmations, secrets, and user data.
- Packaging & Release Engineer for final packaging only.
- Documentation & Support Engineer for docs and troubleshooting.

## Next Recommended Sprint

The current highest-value sprint is:

1. Fix recognition empty-result handling.
2. Add safety preflight before executing compound commands.
3. Introduce runtime stop-event lifecycle for voice mode.
4. Add core tests for matcher, executor, safety, storage, config, and recognizer-worker behavior.
5. Extend diagnostics for command conflicts, model readiness, UI lifecycle, dependencies, microphone, and app paths.
6. Add UI preflight checklist, validation, and config backup/restore.

## Current Constraints

- The project is Windows-oriented.
- Python 3.11 is the target until dependencies are validated for newer Python versions.
- Network-dependent features need API keys or internet access.
- Offline recognition needs Vosk models.
- UI is currently implemented with Tkinter.
