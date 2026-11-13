# Cloud migration audit and implementation plan

## Current baseline

The legacy project currently contains two separate application flows:

- `main_1.py`: local microphone capture through `SpeechRecognition`, local audio playback through `pygame`, Google Speech Recognition (`uk-UA`), gTTS, OpenRouter chat completions, and direct SQL Server access through `pyodbc`.
- `telegram_bot1.py`: Telegram bot handlers, conversation flows, gTTS voice replies, OpenRouter chat completions, and separate direct SQL Server access through `pyodbc`.

Both legacy files contain credentials directly in source code. Treat all exposed OpenRouter credentials and the Telegram bot token as compromised: revoke/rotate them before further use. Remove secrets from tracked files and Git history as part of the security cleanup. Never put replacement credentials in source control.

The SQL Server connection string points to a developer workstation and uses Windows trusted authentication, so it cannot be reused unchanged by a hosted Linux service.

## Target architecture

- One FastAPI backend deployed remotely.
- Telegram bot and browser client call the same application services/API.
- Speech recognition accepts uploaded audio rather than opening a server-side microphone.
- Text-to-speech returns audio bytes or a temporary downloadable response; no local `pygame` playback on the server.
- Database access is isolated behind a repository/service layer.
- Provider credentials and database URLs are injected through environment variables.

## Database decision: pending schema review

PostgreSQL is the leading candidate for a low-cost hosted deployment, but the final decision is deferred until the complete SQL Server schema, constraints, data types, indexes, and any stored procedures are reviewed. The current source files reveal table/column usage but do not provide a complete authoritative schema export.

## Initial implementation status

- [x] Create a non-destructive `cloud-migration` branch.
- [x] Add a minimal FastAPI application with root and health endpoints.
- [x] Add an initial dependency manifest and environment template.
- [ ] Inspect the complete database schema and legacy Telegram handlers.
- [ ] Design and implement the shared domain/service layer.
- [ ] Implement database models and migrations after database selection.
- [ ] Add authenticated REST endpoints and web client.
- [ ] Reconnect Telegram to the shared services.
- [ ] Add audio upload, speech recognition, and speech response endpoints.
- [ ] Add automated tests and performance measurements.
- [ ] Deploy and verify the application on a free/low-cost cloud tier.

## Deployment entry point

After installing `requirements.txt`, run the initial API locally with:

```bash
uvicorn backend.main:app --reload
```

The health check is available at `/health`, and the interactive API documentation is at `/docs`.
