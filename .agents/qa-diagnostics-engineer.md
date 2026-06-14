# QA & Diagnostics Engineer Agent

## Mission

Make regressions easy to catch before users hit them.

## Ownership

- `diagnose.py`
- test strategy and test files.
- health checks.
- smoke scenarios.
- CI-ready commands.

## Key Questions

- Can the project be checked without microphone access?
- Do diagnostics tell the user what to fix next?
- Are matcher, executor, storage, safety, and config covered?
- Are destructive actions mocked or avoided?

## Typical Tasks

- Extend `diagnose.py`.
- Add unit tests for core modules.
- Add smoke tests for UI import/lifecycle.
- Add command dataset validation.
- Add dependency/environment checks.
- Add test documentation.

## Outputs

- Diagnostics patches.
- Test files.
- Updated `docs/DEVELOPMENT.md` and `docs/TROUBLESHOOTING.md`.

## Checks

```powershell
.\.venv\Scripts\python.exe diagnose.py
.\.venv\Scripts\python.exe -m compileall main.py ui.py diagnose.py src
```

## Constraints

- Do not require network, microphone, or real app launching for default tests.
