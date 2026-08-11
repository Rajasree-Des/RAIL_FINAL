# Playwright Automation Engine

Standalone microservice for RailMadad report downloads. **Not embedded in the main FastAPI backend.**

## Responsibilities

- Login to RailMadad portal
- Navigate and apply filters
- Download report files
- Validate downloads (size, extension)
- Store files to shared volume
- Notify backend via callback API

**Does NOT:** process Excel, generate reports, or run business rules.

## Architecture

```
Frontend Dashboard  →  Backend /api/v1/automation/*  →  automation-engine:8003
                              ↑                              |
                              └──────── callback ────────────┘
```

## Run locally

```bash
cd automation-engine
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
python run.py
```

Service listens on **http://127.0.0.1:8003**

Set `DEMO_MODE=true` (default) to simulate downloads without a live portal.

## Internal API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/internal/run` | POST | Start job (Bearer token) |
| `/internal/stop/{id}` | POST | Stop job |
| `/internal/pause/{id}` | POST | Pause job |
| `/internal/resume/{id}` | POST | Resume job |
| `/internal/status/{id}` | GET | Job status |

## Environment

| Variable | Description |
|----------|-------------|
| `SERVICE_TOKEN` | Shared secret with backend |
| `BACKEND_URL` | Main API base URL |
| `DEMO_MODE` | Simulate downloads when true |
| `DOWNLOADS_ROOT` | Root folder for saved files |

## Security

- Credentials passed per-job from backend (decrypted at dispatch time only)
- Log filter redacts password/token/secret strings
- Session state returned encrypted to backend for persistence
- Screenshots saved on failure to `screenshots/`
