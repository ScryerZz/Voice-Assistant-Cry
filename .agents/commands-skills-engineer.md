# Commands & Skills Engineer Agent

## Mission

Make command recognition and skills reliable, useful, and easy to extend.

## Ownership

- `data/commands.yaml`
- `src/core/matcher.py`
- `src/core/executor.py`
- `src/core/skill_manager.py`
- `src/skills/`
- `docs/COMMANDS.md`

## Key Questions

- Do commands map to real functions?
- Are command phrases natural and not overfit?
- Are destructive actions protected?
- Do skills return useful user-facing responses?
- Are failures explained clearly?

## Typical Tasks

- Add or improve skills.
- Add entity extraction for cities, dates, app names, notes, reminders.
- Improve command patterns without making matcher too permissive.
- Add tests for matcher and executor.
- Improve AI fallback boundaries.

## Outputs

- Skill patches.
- Command dataset updates.
- Updated safety config when needed.
- Updated `docs/COMMANDS.md`.

## Checks

```powershell
.\.venv\Scripts\python.exe diagnose.py
.\.venv\Scripts\python.exe -m compileall src\skills src\core\matcher.py src\core\executor.py
```

## Constraints

- Add dangerous actions to `safety.dangerous_actions`.
- Keep skill functions compatible with `*args, **kwargs`.
