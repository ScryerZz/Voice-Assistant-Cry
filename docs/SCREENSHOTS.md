# Screenshots

Store UI screenshots in `docs/assets/screenshots/`.

Use these names so support/docs links stay stable:

| File | Screen |
| --- | --- |
| `01-home.png` | Main screen with process and voice state. |
| `02-chat.png` | Chat with text command and voice-command display. |
| `03-profiles.png` | `Профили` screen with saved assistant profiles. |
| `04-commands.png` | Command list with confirmation column. |
| `05-history.png` | History screen with Russian filters. |
| `06-integrations.png` | API keys and ЯндексGPT/weather/news settings. |
| `07-diagnostics.png` | Diagnostics/support screen with report export. |
| `08-support-report.png` | Opened support report with secrets redacted. |

## Capture Checklist

1. Run `run_settings.bat`.
2. Use a 1280x820 or wider window.
3. Hide personal folders, API keys, and private command text before capture.
4. For support report screenshots, keep `privacy.redact_secrets_in_exports: true`.
5. Update this page if a screen is renamed or removed.

Screenshots are documentation assets, not runtime data. Do not place logs or database exports in this folder.
