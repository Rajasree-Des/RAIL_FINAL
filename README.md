# Railway Report Intelligence Platform

Enterprise Railway Report Automation Platform for generating, processing, and managing railway reports.

## Tech Stack

### Frontend
- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **shadcn/ui** - UI components
- **React Query** - Server state management
- **React Router** - Routing
- **React Hook Form** - Form handling

### Backend
- **Python 3.12** - Runtime
- **FastAPI** - API framework
- **SQLAlchemy** - ORM
- **Alembic** - Database migrations
- **PostgreSQL** - Database
- **Redis** - Caching

## Quick Start

### Prerequisites
- Node.js 22+
- Python 3.12+
- PostgreSQL 16+ (local install)
- Redis 7+ (local install)

### Development Setup

1. **Clone and install dependencies**

```bash
# Frontend
npm install

# Backend
cd backend
pip install -r requirements.txt
```

2. **Start infrastructure**

Ensure PostgreSQL and Redis are running locally and match the URLs in `.env` / `backend/.env` (defaults: `localhost:5432` and `localhost:6379`).

3. **Configure environment**

```bash
# Copy example env files
cp .env.example .env
cp backend/.env.example backend/.env

# Update secrets and default admin credentials for local development
# See backend/README.md#default-admin-account
```

4. **Run database migrations**

```bash
cd backend
alembic upgrade head
```

5. **Start development servers**

```bash
# Terminal 1 - Backend
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 - Frontend
npm run dev
```

6. **Access the application**
- Frontend: http://127.0.0.1:5173
- Backend API: http://127.0.0.1:8000
- API Docs: http://127.0.0.1:8000/docs

## Project Structure

```
├── src/                    # Frontend source
│   ├── app/               # App entry, routing, providers
│   ├── features/          # Feature modules
│   ├── components/        # Shared UI components
│   ├── layouts/           # Layout components
│   ├── context/           # React contexts
│   ├── hooks/             # Custom hooks
│   ├── api/               # API client
│   ├── types/             # TypeScript types
│   └── utils/             # Utility functions
├── backend/               # Backend source
│   ├── app/
│   │   ├── api/           # API routes
│   │   ├── core/          # Configuration, security
│   │   ├── features/      # Feature modules
│   │   ├── domain/        # Domain entities
│   │   └── infrastructure/# Database, repositories
│   ├── alembic/           # Database migrations
│   └── tests/             # Backend tests
├── docs/                  # Documentation
└── scripts/               # Development scripts
```

## Scripts

### Frontend

```bash
npm run dev          # Start dev server
npm run build        # Production build
npm run preview      # Preview production build
npm run test         # Run tests
npm run lint         # Lint code
npm run format       # Format code
npm run ci           # Run CI checks
```

### Backend

```bash
cd backend

# Development
uvicorn app.main:app --reload

# Testing
pytest

# Linting
ruff check .
ruff format .

# Migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Environment Variables

See `.env.example` for all available configuration options.

## Codebase improvements

See [docs/CODEBASE_IMPROVEMENTS.md](docs/CODEBASE_IMPROVEMENTS.md) for architecture notes, security findings, duplicate-code inventory, and the refactor changelog.

## License

Proprietary - Internal Use Only
