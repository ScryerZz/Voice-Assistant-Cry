# Packaging Notes

The current supported packaging path is PyInstaller `onedir` plus an Inno Setup installer.

## Build Commands

Install build tooling into the project venv:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

Build the app folder:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_exe.ps1
```

Build the installer if Inno Setup 6 is installed:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_installer.ps1
```

Current outputs:

```text
dist/CryAssistant/CryAssistant.exe
dist/installer/CryAssistantSetup.exe
```

## Runtime Layout

In source runs, paths stay under the repository `data/` folder.

In PyInstaller builds:

- bundled read-only assets are resolved from `_internal/data`;
- writable user data is resolved from `%APPDATA%/CryAssistant/data`;
- `CryAssistant.exe` starts the UI;
- `CryAssistant.exe --assistant` starts the voice worker;
- `CryAssistant.exe --diagnose` runs diagnostics.
- `CryAssistant.exe --minimized` starts the UI hidden to the tray when the user enabled that behavior.

Autostart is not installed globally by the installer. The first-run wizard can create or remove a per-user Startup shortcut:

```text
%APPDATA%/Microsoft/Windows/Start Menu/Programs/Startup/CryAssistant.lnk
```

This is intentional. Cry needs a user session for the microphone, UI, tray icon, and app-control skills, so it should not be packaged as a Windows Service.

## Include In Application Bundle

- `main.py`, `ui.py`, `diagnose.py`
- `src/`
- `data/commands.yaml`
- `data/media/`
- `requirements.txt` or the resolved dependency lock used for the build
- launcher metadata/scripts required by the selected packaging tool

## Include As Runtime Assets

These are large or user-specific and should not be committed as source files:

- `data/models/stt/` with Vosk models
- `data/models/tts/` with Silero models
- optional initial `data/user_commands.yaml` template if the installer wants to pre-create it

For the current PyInstaller build, models are included under:

```text
dist/CryAssistant/_internal/data/models/stt/vosk-model-small-ru-0.22
dist/CryAssistant/_internal/data/models/stt/vosk-model-small-en-us-0.15
dist/CryAssistant/_internal/data/models/tts/v3_1_ru.pt
dist/CryAssistant/_internal/data/models/tts/v3_en.pt
```

## Keep As User Data

These files must stay writable after installation and should not be embedded read-only inside the executable:

- `data/config.yaml`
- `data/user_commands.yaml`
- `data/assistant.sqlite3`
- `data/logs/`
- `data/runtime/`
- `data/cache/`
- `data/notes.txt`

The current build resolves these to:

```text
%APPDATA%/CryAssistant/data/
```

## Do Not Ship Personal Secrets

Do not ship a public build with real values for:

- `assistant.yandexgpt_api_key`
- `weather.api_key`
- `news.api_key`

Use the UI `Интеграции` screen to fill keys after installation, or provide a private local config only for personal builds.

`tools/prepare_release_data.py` generates a clean bundled config with empty secrets and `first_run_completed: false`.

## Current Model State

Before packaging, diagnostics should show Vosk models as `configured`, not `legacy`, and Silero `.pt` files should be non-empty.

Run:

```powershell
.\.venv\Scripts\python.exe diagnose.py
.\dist\CryAssistant\CryAssistant.exe --diagnose
```

Expected:

- `Vosk models`: paths under `data\models\stt`
- `Silero models`: no missing/empty warning for `v3_1_ru.pt`
