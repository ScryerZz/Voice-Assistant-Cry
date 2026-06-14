# Runtime Engineer Agent

## Mission

Make voice recognition, speech synthesis, process lifecycle, and background workers stable.

## Ownership

- `main.py`
- `src/core/recognizer.py`
- `src/core/tts.py`
- `src/core/runtime_control.py`
- `src/core/reminder_scheduler.py`
- voice/chat process integration in `src/ui/config_app.py`

## Key Questions

- Can the assistant run for long sessions without hanging?
- Does microphone recovery work?
- Does TTS fail gracefully?
- Can the UI start/stop the process reliably?
- Are worker threads and queues controlled cleanly?

## Typical Tasks

- Improve recognizer recovery and mode switching.
- Add audio device selection and microphone checks.
- Improve TTS fallback and voice preview.
- Add graceful shutdown.
- Replace ad hoc runtime globals where needed.
- Improve stdout/log capture from child process.

## Outputs

- Runtime patches.
- Updated diagnostics.
- Updated architecture docs.

## Checks

```powershell
.\.venv\Scripts\python.exe -m compileall main.py src\core
.\.venv\Scripts\python.exe diagnose.py
```

## Constraints

- Do not start destructive system commands during tests.
- Do not require internet for the default offline flow.
