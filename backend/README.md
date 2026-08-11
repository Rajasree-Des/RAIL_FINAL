# Railway Report Platform - Backend

FastAPI backend for the Railway Report Intelligence Platform.

## Setup

### Prerequisites
- Python 3.12+
- PostgreSQL 16+
- Redis 7+

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser drivers (one-time, for automation)
playwright install chromium

# Copy environment file
cp .env.example .env
```

### Database Setup

```bash
# Ensure PostgreSQL is installed and running locally (default localhost:5432)

# Run migrations
alembic upgrade head
```

### Running

```bash
# Development with auto-reload
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Project Structure

```
backend/
├── app/
│   ├── api/               # API routes
│   │   └── v1/           # API version 1
│   │       └── router.py # Route aggregation
│   ├── core/              # Core configuration
│   │   ├── config.py     # Settings management
│   │   ├── security/     # Security utilities
│   │   ├── logging.py    # Logging setup
│   │   ├── exceptions.py # Custom exceptions
│   │   ├── error_handlers.py
│   │   └── middleware.py
│   ├── features/          # Feature modules
│   │   ├── auth/         # Authentication
│   │   ├── workflows/    # Workflow management
│   │   ├── uploads/      # File uploads
│   │   └── health/       # Health checks
│   ├── domain/            # Domain layer
│   │   ├── entities/     # Domain entities
│   │   └── interfaces/   # Repository interfaces
│   └── infrastructure/    # Infrastructure layer
│       ├── database/     # Database configuration
│       ├── repositories/ # Repository implementations
│       └── seed/         # Data seeders
├── alembic/               # Database migrations
├── tests/                 # Test suite
├── uploads/               # Uploaded files (gitignored)
├── requirements.txt
├── pyproject.toml         # Ruff config, pytest config
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/features/workflows/test_controller.py
```

## Linting

```bash
# Check code
ruff check .

# Fix auto-fixable issues
ruff check --fix .

# Format code
ruff format .

# CI script (check + test)
python scripts/ci.ps1  # On Windows
```

## API Documentation

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- OpenAPI JSON: http://127.0.0.1:8000/openapi.json

## Database Migrations

```bash
# Generate migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## Feature Development

Each feature follows this structure:

```
features/
└── feature_name/
    ├── __init__.py
    ├── controller.py    # API endpoints
    ├── service.py       # Business logic
    ├── repository.py    # Data access
    ├── schemas.py       # Pydantic schemas
    ├── validation.py    # Input validation
    └── dependencies.py  # FastAPI dependencies
```

## Environment Variables

See `.env.example` for all configuration options.

### Default Admin Account

On startup, the backend can create a default admin user if one does not already exist. Configure credentials in `backend/.env` (copy from `backend/.env.example`):

```env
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=Admin@123456
```

- Set both variables to your own local dev credentials before first run.
- The user is created with the `admin` role; email is derived as `{username}@railway.local`.
- Seeding is **idempotent**: if the username already exists, nothing is changed (password is not overwritten).
- If either variable is missing or blank, seeding is skipped and a warning is logged.
- Sign in via the normal login endpoint (`POST /api/v1/auth/login`); no auth bypass is used.

## In-Process Automation (`app/automation`)

Playwright-based browser automation (separate from `features/automation`, which orchestrates the standalone automation-engine service):

```
app/automation/
├── __init__.py
├── browser.py       # CDP browser connection
├── config.py        # Env-based settings
├── session.py       # Session/tab management (Phase 3+)
├── navigation.py    # Portal navigation (Phase 4+)
├── downloader.py    # Report downloads (Phase 5+)
├── reports.py       # Report catalog
├── selectors.py     # Portal UI selectors
├── utils.py         # Shared helpers
└── run.py           # Smoke-test entrypoint
```

Verify Phase 1 setup:

```bash
pytest tests/automation/test_module_structure.py -v
python -m app.automation.run   # requires Chrome with --remote-debugging-port=9222
```

### Required for Production
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `JWT_SECRET_KEY` - Min 32 characters, cryptographically random
- `CSRF_SECRET_KEY` - Cryptographically random
- `COOKIE_SECURE=true` - Enable for HTTPS
- `ENVIRONMENT=production`
