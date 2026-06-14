# Конфигурация

Основной файл настроек пользователя:

```text
data/config.yaml
```

Дефолты находятся в `src/core/config.py`. При загрузке проекта пользовательский YAML объединяется с дефолтами, поэтому отсутствующий ключ не обязан ломать запуск.

Обычному пользователю лучше менять настройки через `run_settings.bat`.

## Верхний Уровень

| Ключ | Тип | Назначение |
| --- | --- | --- |
| `voice_enabled` | `bool` | Озвучивать ответы. |
| `voice_engine` | `str` | `silero` или `pyttsx3`. |
| `voice_speed` | `int` | Скорость `pyttsx3`. |
| `voice_volume` | `float` | Громкость от `0.0` до `1.0`. |
| `voice_gender` | `str` | Предпочитаемый пол голоса. |
| `voice_speaker` | `str` | Спикер Silero. |
| `language` | `str` | Локаль распознавания, например `ru-RU`. |
| `wake_word` | `str` | Старый одиночный wake word для совместимости. |
| `wake_words` | `dict` | Слова активации по языкам. |
| `debug` | `bool` | Подробный лог. |
| `offline_mode` | `bool` | Офлайн-режим распознавания. |
| `auto_switch_mode` | `bool` | Автопереключение онлайн/офлайн. |
| `first_run_completed` | `bool` | Завершён ли мастер первого запуска. |
| `startup` | `dict` | Автозапуск Windows и поведение трея. |
| `privacy` | `dict` | Настройки приватности support-экспорта. |
| `profiles` | `dict` | Профили ассистента. |

## Assistant

```yaml
assistant:
  name: Cry
  default_language: ru
  voice: default
  personality: friendly
  ai_enabled: true
  yandexgpt_api_key: ''
  yandex_folder_id: ''
```

| Ключ | Назначение |
| --- | --- |
| `assistant.name` | Имя в UI и ответах. |
| `assistant.default_language` | `ru` или `en`. |
| `assistant.voice` | Зарезервированный профиль голоса. |
| `assistant.personality` | Стиль общения. |
| `assistant.ai_enabled` | Использовать ЯндексGPT для неизвестных фраз. |
| `assistant.yandexgpt_api_key` | API-ключ ЯндексGPT. |
| `assistant.yandex_folder_id` | ID каталога Яндекс Облака. |

ЯндексGPT работает только если включён `ai_enabled` и заполнены оба поля: API-ключ и ID каталога.

## Recognition

```yaml
recognition:
  online_listen_seconds: 5
  offline_listen_timeout_seconds: 8
  audio_queue_timeout_seconds: 1.0
  recover_after_errors: 3
  miss_threshold: 3
  repeat_prompt_enabled: true
```

| Ключ | Назначение |
| --- | --- |
| `online_listen_seconds` | Длина онлайн-записи. |
| `offline_listen_timeout_seconds` | Окно ожидания Vosk. |
| `audio_queue_timeout_seconds` | Тайм-аут очереди аудио. |
| `recover_after_errors` | Ошибок до восстановления микрофонного потока. |
| `miss_threshold` | Пустых распознаваний до подсказки повторить. |
| `repeat_prompt_enabled` | Говорить ли `повторите`. |

## Matcher

```yaml
matcher:
  threshold: 68
  partial_threshold: 78
  smalltalk_threshold: 45
  min_partial_length: 5
```

Если ассистент часто не находит команды, снижайте пороги осторожно. Если выполняет не те команды, повышайте.

## Voice / TTS

```yaml
voice_enabled: true
voice_engine: silero
voice_speed: 180
voice_volume: 1.0
voice_gender: female
voice_speaker: aidar
silero:
  ru_speakers: [aidar, baya, kseniya, xenia, eugene]
  en_speakers: [en_0, en_1, en_2]
  sample_rate: 48000
  use_cuda: true
```

Silero даёт более качественный голос, но зависит от Torch и модели `.pt`. Если модель отсутствует, runtime падает обратно на `pyttsx3`.

## Paths

```yaml
paths:
  datasets: data/commands.yaml
  user_commands: data/user_commands.yaml
  tts_models: data/models/tts
  stt_models: data/models/stt
  cache_dir: data/cache
  database: data/assistant.sqlite3
```

Относительные пути считаются от корня проекта.

## Startup / Tray

```yaml
startup:
  launch_on_login: false
  start_minimized_to_tray: true
  minimize_to_tray_on_close: true
  start_assistant_on_launch: false
```

| Ключ | Назначение |
| --- | --- |
| `launch_on_login` | Создавать ярлык Cry в автозагрузке текущего пользователя Windows. |
| `start_minimized_to_tray` | При автозапуске открывать приложение скрытым в системном трее. |
| `minimize_to_tray_on_close` | Сворачивать окно в трей при нажатии на крестик. |
| `start_assistant_on_launch` | Автоматически запускать голосовой runtime после открытия UI. |

Это не Windows Service. Ассистент запускается в пользовательской сессии, чтобы иметь доступ к UI, микрофону и системному трею.

## Profiles

```yaml
profiles:
  active: home
  items:
    home:
      label: Дом
      created_at: '2026-06-10 12:00:00'
      settings:
        assistant.name: Cry
        assistant.default_language: ru
        voice_engine: silero
```

Профили хранят персонализацию: язык, голос, wake words, режим и приватность. API-ключи и пути приложений не сохраняются.

## Privacy

```yaml
privacy:
  redact_secrets_in_exports: true
  include_logs_in_reports: true
  include_history_in_reports: false
  crash_summary_lines: 80
```

| Ключ | Назначение |
| --- | --- |
| `redact_secrets_in_exports` | Скрывать API-ключи в support-отчётах. |
| `include_logs_in_reports` | Включать последние строки логов. |
| `include_history_in_reports` | Включать историю команд. По умолчанию выключено. |
| `crash_summary_lines` | Сколько строк ошибок включать в crash summary. |

## Weather / News

```yaml
weather:
  api_key: ''
  default_city: Казань
news:
  api_key: ''
```

Если ключи пустые, навыки должны вернуть понятное сообщение или открыть fallback.

## System Power

```yaml
system_power:
  shutdown_delay_seconds: 30
```

`shutdown_delay_seconds` задаёт задержку перед выключением или перезагрузкой после подтверждения. Значение ограничивается безопасным диапазоном 5-600 секунд.

## Safety

```yaml
safety:
  confirm_dangerous_commands: true
  confirmation_timeout_seconds: 15
  dangerous_min_score: 90
  dangerous_actions:
    - system.shutdown
    - system.restart
    - history.clear_history
```

Все действия, которые закрывают приложения, очищают данные, выключают/перезагружают систему или удаляют файлы, должны быть в `dangerous_actions`.

## Apps

```yaml
apps:
  telegram:
    path: C:/Users/user/AppData/Roaming/Telegram Desktop/Telegram.exe
    process: Telegram.exe
```

Каждая запись может содержать:

| Ключ | Назначение |
| --- | --- |
| `display_name` | Имя в UI и ответах. |
| `aliases` | Дополнительные названия для распознавания. |
| `path` | Путь к `.exe` или ярлыку. |
| `process` | Имя процесса для закрытия/статуса. |

## Runtime Control

```json
{
  "voice_listening_enabled": true
}
```

Файл `data/runtime/control.json` используется UI-переключателем голоса и читается работающим `main.py`.

## Проверки После Изменений

```powershell
.\.venv\Scripts\python.exe diagnose.py
.\.venv\Scripts\python.exe -m compileall main.py ui.py diagnose.py src tests
```
