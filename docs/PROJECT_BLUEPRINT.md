# Railway Report Automation Platform - Project Blueprint

**Version:** 1.0  
**Date:** July 4, 2026  
**Status:** Planning Phase

---

## Table of Contents

1. [Folder Structure](#1-folder-structure)
2. [High Level Architecture](#2-high-level-architecture)
3. [Low Level Architecture](#3-low-level-architecture)
4. [Module Dependency Diagram](#4-module-dependency-diagram)
5. [Database ER Diagram](#5-database-er-diagram)
6. [API List](#6-api-list)
7. [User Roles](#7-user-roles)
8. [Processing Pipeline](#8-processing-pipeline)
9. [Automation Pipeline](#9-automation-pipeline)
10. [Security Architecture](#10-security-architecture)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Folder Responsibilities](#12-folder-responsibilities)
13. [Naming Conventions](#13-naming-conventions)
14. [API Standards](#14-api-standards)
15. [Error Handling Strategy](#15-error-handling-strategy)
16. [Logging Strategy](#16-logging-strategy)
17. [Configuration Strategy](#17-configuration-strategy)
18. [Future Scalability Strategy](#18-future-scalability-strategy)

---

## 1. Folder Structure

```
railway-platform/
├── frontend/                      # React 19 + TypeScript SPA
│   ├── src/
│   │   ├── api/                   # API clients and response mappers
│   │   │   └── schemas/           # Zod validation schemas
│   │   ├── app/                   # Application entry point
│   │   ├── components/
│   │   │   └── ui/                # Reusable UI primitives (shadcn/ui style)
│   │   ├── context/               # React Context providers
│   │   ├── features/              # Feature modules
│   │   │   ├── auth/              # Authentication UI
│   │   │   ├── dashboard/         # Dashboard views
│   │   │   ├── workflows/         # Workflow panels
│   │   │   └── admin/             # Admin management UI
│   │   ├── hooks/                 # Shared custom hooks
│   │   ├── layouts/               # Page layouts
│   │   ├── styles/                # Global CSS
│   │   ├── types/                 # TypeScript type definitions
│   │   └── utils/                 # Utility functions
│   ├── public/                    # Static assets
│   └── tests/                     # Frontend tests
│
├── backend/                       # FastAPI Backend (API Gateway)
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/                # API version 1 router
│   │   ├── core/                  # Core infrastructure
│   │   │   └── security/          # Security modules
│   │   ├── domain/                # Domain layer
│   │   │   ├── entities/          # Domain entities (dataclasses)
│   │   │   └── interfaces/        # Repository interfaces (ABCs)
│   │   ├── features/              # Feature modules
│   │   │   ├── auth/              # Authentication feature
│   │   │   ├── health/            # Health check
│   │   │   ├── uploads/           # File upload handling
│   │   │   ├── workflows/         # Workflow configuration
│   │   │   ├── reports/           # Report orchestration
│   │   │   └── admin/             # Admin operations
│   │   └── infrastructure/        # Infrastructure layer
│   │       ├── database/          # SQLAlchemy models, session
│   │       ├── repositories/      # Shared repositories
│   │       └── seed/              # Database seeders
│   ├── alembic/                   # Database migrations
│   ├── tests/                     # Backend tests
│   └── uploads/                   # File upload storage
│
├── report-engine/                 # Report Processing Engine (Microservice)
│   ├── app/
│   │   ├── api/                   # Internal API
│   │   ├── core/                  # Core config
│   │   ├── processors/            # Excel/CSV processors
│   │   │   ├── readers/           # File readers
│   │   │   ├── transformers/      # Data transformers
│   │   │   └── writers/           # Output writers
│   │   ├── templates/             # Report templates
│   │   └── validators/            # Data validators
│   └── tests/
│
├── rule-engine/                   # Business Rule Engine (Microservice)
│   ├── app/
│   │   ├── api/                   # Internal API
│   │   ├── core/                  # Core config
│   │   ├── rules/                 # Rule definitions
│   │   │   ├── division/          # Division-specific rules
│   │   │   ├── train/             # Train-specific rules
│   │   │   └── complaint/         # Complaint type rules
│   │   ├── evaluator/             # Rule evaluation engine
│   │   └── aggregator/            # Result aggregation
│   └── tests/
│
├── automation-engine/             # Playwright Automation (Microservice)
│   ├── app/
│   │   ├── api/                   # Internal API
│   │   ├── core/                  # Core config
│   │   ├── scrapers/              # Web scrapers
│   │   │   ├── railmadad/         # RailMadad scraper
│   │   │   └── irctc/             # IRCTC data scraper
│   │   ├── downloaders/           # File downloaders
│   │   └── scheduler/             # Job scheduler
│   └── tests/
│
├── shared/                        # Shared resources
│   ├── openapi/                   # OpenAPI specifications
│   ├── schemas/                   # Shared JSON schemas
│   └── constants/                 # Shared constants
│
├── docs/                          # Documentation
│   ├── architecture/              # Architecture diagrams
│   ├── api/                       # API documentation
│   └── deployment/                # Deployment guides
│
├── infrastructure/                # Infrastructure as Code
│   ├── kubernetes/                # K8s manifests
│   └── terraform/                 # Cloud provisioning
│
└── scripts/                       # Development scripts
    ├── setup/                     # Setup scripts
    └── ci/                        # CI/CD scripts
```

### Decision Rationale

| Decision | Rationale |
|----------|-----------|
| **Monorepo structure** | Simplifies dependency management, enables atomic commits across services, easier local development |
| **Feature-based organization** | Each feature is self-contained with its own controller/service/repository, enabling independent testing and deployment |
| **Separate microservices** | Report engine, rule engine, and automation engine are isolated for independent scaling and technology choices |
| **Shared folder** | Common schemas and constants prevent duplication and ensure consistency |
| **Infrastructure folder** | IaC enables reproducible deployments and environment parity |

---

## 2. High Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     React 19 SPA (Frontend)                          │   │
│  │  • Authentication UI    • Workflow Panels    • Admin Dashboard       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTPS (REST API)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY LAYER                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     FastAPI Backend (API Gateway)                    │   │
│  │  • Authentication/Authorization  • Request Validation               │   │
│  │  • Rate Limiting                 • Request Routing                  │   │
│  │  • Audit Logging                 • Response Transformation          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────────┐
│   Report Processing   │ │   Business Rule   │ │     Automation        │
│        Engine         │ │      Engine       │ │       Engine          │
│  ─────────────────── │ │  ───────────────  │ │  ───────────────────  │
│  • Excel Processing   │ │  • Rule Eval      │ │  • Web Scraping       │
│  • CSV Parsing        │ │  • Aggregation    │ │  • File Download      │
│  • Data Transform     │ │  • Scoring        │ │  • Scheduling         │
│  • Report Generation  │ │  • Ranking        │ │  • Browser Automation │
└───────────────────────┘ └───────────────────┘ └───────────────────────┘
                    │                 │                 │
                    └─────────────────┼─────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐   │
│  │   PostgreSQL   │  │     Redis      │  │      Object Storage        │   │
│  │   (Primary DB) │  │    (Cache)     │  │   (Files & Reports)        │   │
│  └────────────────┘  └────────────────┘  └────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Decision Rationale

| Decision | Rationale |
|----------|-----------|
| **Single Page Application** | Better UX for data-heavy dashboard, offline capability, reduces server load |
| **API Gateway Pattern** | Centralized authentication, rate limiting, and request routing; simplifies frontend integration |
| **Microservices for engines** | Each engine has different scaling needs and technology requirements; isolation prevents cascading failures |
| **PostgreSQL** | ACID compliance for transactional data, JSON support for flexible schemas, excellent query performance |
| **Redis** | Session storage, rate limiting counters, caching frequently accessed configurations |
| **Object Storage** | Scalable file storage for uploads and generated reports |

---

## 3. Low Level Architecture

### 3.1 Backend (FastAPI) - Clean Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API LAYER (Controllers)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ AuthController│ │WorkflowCtrl │  │ ReportCtrl  │  ...        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                      │
│         ▼                ▼                ▼                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 Pydantic Schemas (DTOs)                  │   │
│  │        Request Validation    Response Serialization      │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER (Services)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ AuthService │  │WorkflowSvc  │  │ ReportSvc   │  ...        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                      │
│         │    Business Logic Orchestration                       │
│         │    • Validation beyond Pydantic                       │
│         │    • Cross-entity operations                          │
│         │    • External service calls                           │
│         ▼                ▼                ▼                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DOMAIN LAYER (Core)                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Domain Entities                       │   │
│  │     User    Workflow    Report    BusinessRule           │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Repository Interfaces                   │   │
│  │   IUserRepository   IWorkflowRepository   IReportRepo    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   INFRASTRUCTURE LAYER                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  SQLAlchemy │  │   Redis     │  │  External   │             │
│  │   Repos     │  │   Client    │  │   APIs      │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Database Models (ORM)                       │   │
│  │   UserModel   WorkflowModel   ReportModel   ...          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Frontend (React) - Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       PRESENTATION LAYER                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                     Page Components                      │   │
│  │    WorkflowPage    DashboardPage    AdminPage            │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                             │                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Feature Components                    │   │
│  │   ReportPanel   MergingPanel   SummaryPanel   SettingsUI │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                             │                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                      UI Components                       │   │
│  │   Button   Card   Input   Select   Alert   Spinner       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         STATE LAYER                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    React Context                         │   │
│  │   AuthContext   WorkflowConfigContext   SessionContext   │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Custom Hooks                          │   │
│  │   useAuth   useWorkflowActions   useSummaryGeneration    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DATA ACCESS LAYER                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                     API Clients                          │   │
│  │   authApi   workflowApi   reportApi   uploadApi          │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Zod Schemas                            │   │
│  │   Response validation   Type inference                   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Decision Rationale

| Decision | Rationale |
|----------|-----------|
| **Clean Architecture layers** | Dependency inversion allows swapping infrastructure without changing business logic |
| **Domain entities as dataclasses** | Immutable, framework-agnostic, easy to test |
| **Repository interfaces** | Abstraction enables mocking for tests and future database changes |
| **Pydantic for DTOs** | Automatic validation, serialization, and documentation generation |
| **React Context over Redux** | Simpler for this app's scale; avoids boilerplate |
| **Hooks for business logic** | Separates logic from presentation; enables reuse and testing |

---

## 4. Module Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND MODULES                                │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
    │   App    │────▶│  Router  │────▶│ Layouts  │────▶│  Pages   │
    └──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                             │
         ┌───────────────────────────────────────────────────┤
         │                       │                           │
         ▼                       ▼                           ▼
    ┌──────────┐          ┌──────────┐               ┌──────────┐
    │ Context  │◀─────────│  Hooks   │◀──────────────│ Features │
    │Providers │          │          │               │Components│
    └──────────┘          └──────────┘               └──────────┘
         │                       │                           │
         └───────────────────────┼───────────────────────────┘
                                 │
                                 ▼
                          ┌──────────┐
                          │   API    │
                          │ Clients  │
                          └──────────┘
                                 │
                                 ▼
                          ┌──────────┐
                          │    UI    │
                          │Components│
                          └──────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND MODULES                                 │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────┐     ┌──────────┐     ┌──────────┐
    │   Main   │────▶│  Router  │────▶│Controllers│
    │  (App)   │     │          │     │          │
    └──────────┘     └──────────┘     └──────────┘
         │                                  │
         │                                  ▼
         │           ┌──────────────────────────────────────┐
         │           │              Services                │
         │           │  ┌────────┐ ┌────────┐ ┌────────┐  │
         │           │  │  Auth  │ │Workflow│ │ Report │  │
         │           │  │Service │ │Service │ │Service │  │
         │           │  └────────┘ └────────┘ └────────┘  │
         │           └──────────────────────────────────────┘
         │                                  │
         ▼                                  ▼
    ┌──────────┐     ┌──────────────────────────────────────┐
    │   Core   │     │            Domain Layer              │
    │ Security │     │  ┌────────┐ ┌────────┐ ┌────────┐  │
    │  Config  │     │  │Entities│ │  Repo  │ │Excepts │  │
    │ Logging  │     │  │        │ │Interfce│ │        │  │
    └──────────┘     │  └────────┘ └────────┘ └────────┘  │
         │           └──────────────────────────────────────┘
         │                                  │
         └──────────────────────────────────┤
                                            ▼
                     ┌──────────────────────────────────────┐
                     │           Infrastructure             │
                     │  ┌────────┐ ┌────────┐ ┌────────┐  │
                     │  │Database│ │ Repos  │ │External│  │
                     │  │Session │ │        │ │  APIs  │  │
                     │  └────────┘ └────────┘ └────────┘  │
                     └──────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           INTER-SERVICE DEPENDENCIES                         │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌───────────┐          ┌───────────┐          ┌───────────┐
    │  Backend  │─────────▶│  Report   │─────────▶│   Rule    │
    │  (API)    │          │  Engine   │          │  Engine   │
    └───────────┘          └───────────┘          └───────────┘
         │                       │                      │
         │                       └──────────────────────┘
         │                                 │
         ▼                                 ▼
    ┌───────────┐                   ┌───────────┐
    │Automation │                   │ PostgreSQL│
    │  Engine   │                   │  + Redis  │
    └───────────┘                   └───────────┘
```

### Dependency Rules

1. **Inward dependencies only**: Outer layers depend on inner layers, never the reverse
2. **Domain has no dependencies**: Domain entities and interfaces are pure Python
3. **Services don't know about HTTP**: They work with domain objects, not requests/responses
4. **Frontend features don't import each other**: Communication through context/props only

---

## 5. Database ER Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AUTHENTICATION                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────┐          ┌─────────────────────────┐
│         users           │          │     refresh_tokens      │
├─────────────────────────┤          ├─────────────────────────┤
│ PK id: UUID             │──────┐   │ PK id: SERIAL           │
│    username: VARCHAR(64)│      │   │ FK user_id: UUID        │──┐
│    email: VARCHAR(255)  │      │   │    token_hash: VARCHAR  │  │
│    password_hash: TEXT  │      │   │    expires_at: TIMESTAMP│  │
│    role: VARCHAR(32)    │      │   │    revoked_at: TIMESTAMP│  │
│    is_active: BOOLEAN   │      │   │    created_at: TIMESTAMP│  │
│    created_at: TIMESTAMP│      │   └─────────────────────────┘  │
│    updated_at: TIMESTAMP│      │                                │
│    last_login: TIMESTAMP│      └────────────────────────────────┘
└─────────────────────────┘              1:N relationship

┌─────────────────────────────────────────────────────────────────────────────┐
│                              WORKFLOW CONFIGURATION                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────┐
│       workflows         │
├─────────────────────────┤
│ PK id: VARCHAR(64)      │──────┬───────────┬───────────┬───────────┐
│    name: VARCHAR(128)   │      │           │           │           │
│    order: INTEGER       │      │           │           │           │
│    description: TEXT    │      │           │           │           │
│    variant: VARCHAR(32) │      │           │           │           │
│    icon: VARCHAR(32)    │      │           │           │           │
│    upload_label: TEXT   │      │           │           │           │
│    report_source_id: VAR│      │           │           │           │
│    accepted_files: TEXT │      │           │           │           │
│    created_at: TIMESTAMP│      │           │           │           │
│    updated_at: TIMESTAMP│      │           │           │           │
└─────────────────────────┘      │           │           │           │
         │                       │           │           │           │
         │ 1:N                   │ 1:N       │ 1:N       │ 1:N       │
         ▼                       ▼           ▼           ▼           │
┌──────────────────┐  ┌──────────────────┐ ┌────────────────┐ ┌─────────────────┐
│workflow_settings │  │ column_mappings  │ │business_rules  │ │report_templates │
├──────────────────┤  ├──────────────────┤ ├────────────────┤ ├─────────────────┤
│PK id: SERIAL     │  │PK id: SERIAL     │ │PK id: SERIAL   │ │PK id: SERIAL    │
│FK workflow_id    │  │FK workflow_id    │ │FK workflow_id  │ │FK workflow_id   │
│   setting_id     │  │   key            │ │   rule_id      │ │   template_id   │
│   label          │  │   label          │ │   name         │ │   name          │
│   type           │  │   column_type    │ │   rule_type    │ │   template_type │
│   required       │  │   required       │ │   expression   │ │   content       │
│   placeholder    │  │   source_column  │ │   severity     │ │   output_format │
│   default_value  │  │   sort_order     │ │   enabled      │ └─────────────────┘
│   options_json   │  └──────────────────┘ └────────────────┘
│   help_text      │
│   sort_order     │
└──────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              REPORT PROCESSING                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────┐          ┌─────────────────────────┐
│     uploaded_files      │          │        reports          │
├─────────────────────────┤          ├─────────────────────────┤
│ PK id: UUID             │          │ PK id: UUID             │
│ FK user_id: UUID        │──┐       │ FK user_id: UUID        │──┐
│ FK workflow_id: VARCHAR │  │       │ FK workflow_id: VARCHAR │  │
│    original_filename    │  │       │ FK upload_id: UUID      │  │
│    stored_filename      │  │       │    status: VARCHAR      │  │
│    file_size: BIGINT    │  │       │    settings_json: JSONB │  │
│    content_type         │  │       │    result_path: TEXT    │  │
│    uploaded_at          │  │       │    error_message: TEXT  │  │
│    status: VARCHAR      │  │       │    started_at           │  │
└─────────────────────────┘  │       │    completed_at         │  │
                             │       │    created_at           │  │
                             │       └─────────────────────────┘  │
                             │                                    │
┌─────────────────────────┐  │       ┌─────────────────────────┐  │
│      audit_logs         │  │       │    report_downloads     │  │
├─────────────────────────┤  │       ├─────────────────────────┤  │
│ PK id: SERIAL           │  │       │ PK id: SERIAL           │  │
│ FK user_id: UUID        │──┘       │ FK report_id: UUID      │  │
│    action: VARCHAR      │          │ FK user_id: UUID        │──┘
│    resource_type        │          │    downloaded_at        │
│    resource_id          │          │    format: VARCHAR      │
│    ip_address           │          │    ip_address           │
│    user_agent           │          └─────────────────────────┘
│    details_json: JSONB  │
│    success: BOOLEAN     │
│    created_at           │
└─────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              AUTOMATION                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────┐          ┌─────────────────────────┐
│    automation_jobs      │          │   automation_schedules  │
├─────────────────────────┤          ├─────────────────────────┤
│ PK id: UUID             │          │ PK id: UUID             │
│ FK schedule_id: UUID    │◀─────────│    name: VARCHAR        │
│    job_type: VARCHAR    │          │    cron_expression      │
│    status: VARCHAR      │          │    source_type          │
│    parameters_json      │          │    parameters_json      │
│    result_path: TEXT    │          │    is_active: BOOLEAN   │
│    error_message        │          │    last_run_at          │
│    started_at           │          │    next_run_at          │
│    completed_at         │          │    created_at           │
│    created_at           │          └─────────────────────────┘
└─────────────────────────┘
```

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| **UUID for entity IDs** | Globally unique, can be generated client-side, no auto-increment bottleneck |
| **SERIAL for junction tables** | Simpler for tables that are never referenced externally |
| **JSONB for flexible data** | Settings and parameters vary by workflow; JSONB allows schema evolution |
| **Soft deletes (is_active)** | Audit trail preservation; easier data recovery |
| **Separate audit_logs table** | High write volume shouldn't impact main tables; can be archived separately |
| **Normalized workflow config** | Settings, columns, rules are separate tables for flexibility and reuse |

---

## 6. API List

### 6.1 Authentication APIs

| Method | Endpoint | Description | Auth | Roles |
|--------|----------|-------------|------|-------|
| POST | `/api/v1/auth/login` | Authenticate user | No | - |
| POST | `/api/v1/auth/register` | Register new user | No | - |
| POST | `/api/v1/auth/refresh` | Refresh access token | Cookie | - |
| POST | `/api/v1/auth/logout` | Invalidate session | Yes | Any |
| GET | `/api/v1/auth/me` | Get current user | Yes | Any |
| POST | `/api/v1/auth/change-password` | Change password | Yes | Any |

### 6.2 Workflow APIs

| Method | Endpoint | Description | Auth | Roles |
|--------|----------|-------------|------|-------|
| GET | `/api/v1/workflows` | List all workflows | Yes | Any |
| GET | `/api/v1/workflows/{id}` | Get workflow config | Yes | Any |
| PUT | `/api/v1/workflows/{id}` | Update workflow | Yes | Admin |
| GET | `/api/v1/workflows/{id}/settings` | Get workflow settings | Yes | Any |
| PUT | `/api/v1/workflows/{id}/settings` | Update settings | Yes | Admin |

### 6.3 Upload APIs

| Method | Endpoint | Description | Auth | Roles |
|--------|----------|-------------|------|-------|
| POST | `/api/v1/uploads` | Upload file | Yes | Officer+ |
| GET | `/api/v1/uploads` | List user uploads | Yes | Officer+ |
| GET | `/api/v1/uploads/{id}` | Get upload details | Yes | Officer+ |
| DELETE | `/api/v1/uploads/{id}` | Delete upload | Yes | Officer+ |

### 6.4 Report APIs

| Method | Endpoint | Description | Auth | Roles |
|--------|----------|-------------|------|-------|
| POST | `/api/v1/reports/generate` | Start report generation | Yes | Officer+ |
| GET | `/api/v1/reports` | List user reports | Yes | Officer+ |
| GET | `/api/v1/reports/{id}` | Get report details | Yes | Officer+ |
| GET | `/api/v1/reports/{id}/status` | Get generation status | Yes | Officer+ |
| GET | `/api/v1/reports/{id}/download` | Download report | Yes | Officer+ |
| POST | `/api/v1/reports/{id}/regenerate` | Regenerate report | Yes | Officer+ |

### 6.5 Summary APIs

| Method | Endpoint | Description | Auth | Roles |
|--------|----------|-------------|------|-------|
| POST | `/api/v1/summaries/generate` | Generate summary | Yes | Officer+ |
| GET | `/api/v1/summaries/{id}` | Get summary | Yes | Officer+ |
| GET | `/api/v1/summaries/{id}/whatsapp` | Get WhatsApp format | Yes | Officer+ |
| GET | `/api/v1/summaries/{id}/email` | Get email format | Yes | Officer+ |
| GET | `/api/v1/summaries/{id}/pdf` | Download PDF | Yes | Officer+ |

### 6.6 Admin APIs

| Method | Endpoint | Description | Auth | Roles |
|--------|----------|-------------|------|-------|
| GET | `/api/v1/admin/users` | List all users | Yes | Admin |
| POST | `/api/v1/admin/users` | Create user | Yes | Admin |
| PUT | `/api/v1/admin/users/{id}` | Update user | Yes | Admin |
| DELETE | `/api/v1/admin/users/{id}` | Deactivate user | Yes | Admin |
| PUT | `/api/v1/admin/users/{id}/role` | Change user role | Yes | Admin |
| GET | `/api/v1/admin/audit-logs` | Get audit logs | Yes | Admin |
| GET | `/api/v1/admin/statistics` | Get system stats | Yes | Admin |

### 6.7 Automation APIs (Internal)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/automation/jobs` | Create job | Service |
| GET | `/api/v1/automation/jobs/{id}` | Get job status | Service |
| GET | `/api/v1/automation/schedules` | List schedules | Service |
| POST | `/api/v1/automation/schedules` | Create schedule | Service |

### 6.8 Health APIs

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/health` | Health check | No |
| GET | `/api/v1/health/ready` | Readiness check | No |
| GET | `/api/v1/health/live` | Liveness check | No |

---

## 7. User Roles

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ROLE HIERARCHY                                  │
└─────────────────────────────────────────────────────────────────────────────┘

                            ┌─────────────┐
                            │    ADMIN    │
                            │  (Level 3)  │
                            └──────┬──────┘
                                   │ inherits
                                   ▼
                            ┌─────────────┐
                            │   OFFICER   │
                            │  (Level 2)  │
                            └──────┬──────┘
                                   │ inherits
                                   ▼
                            ┌─────────────┐
                            │   VIEWER    │
                            │  (Level 1)  │
                            └─────────────┘
```

### Role Definitions

| Role | Description | Use Case |
|------|-------------|----------|
| **VIEWER** | Read-only access to dashboards and reports | Supervisory officers who only need to view reports |
| **OFFICER** | Can generate reports and upload files | Working officers who process complaints |
| **ADMIN** | Full system access including user management | IT administrators and system managers |

### Permission Matrix

| Permission | Viewer | Officer | Admin |
|------------|--------|---------|-------|
| View workflows | ✅ | ✅ | ✅ |
| View reports | ✅ | ✅ | ✅ |
| Upload files | ❌ | ✅ | ✅ |
| Generate reports | ❌ | ✅ | ✅ |
| Generate summaries | ❌ | ✅ | ✅ |
| Download reports | ✅ | ✅ | ✅ |
| Manage own profile | ✅ | ✅ | ✅ |
| Manage users | ❌ | ❌ | ✅ |
| View audit logs | ❌ | ❌ | ✅ |
| Configure workflows | ❌ | ❌ | ✅ |
| Manage automation | ❌ | ❌ | ✅ |
| System configuration | ❌ | ❌ | ✅ |

### Decision Rationale

| Decision | Rationale |
|----------|-----------|
| **Three-tier hierarchy** | Matches Indian Railway organizational structure; simple enough to understand |
| **Role inheritance** | Higher roles automatically get lower role permissions; reduces configuration |
| **Viewer as base role** | Ensures new users have minimal permissions by default (principle of least privilege) |
| **Officer for data operations** | Separates data processors from administrators |

---

## 8. Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         REPORT GENERATION PIPELINE                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Upload  │───▶│ Validate │───▶│  Parse   │───▶│Transform │───▶│ Generate │
│   File   │    │   File   │    │   Data   │    │   Data   │    │  Report  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Store   │    │ Validate │    │ Extract  │    │  Apply   │    │  Format  │
│Metadata  │    │Extension │    │  Rows    │    │  Rules   │    │  Output  │
│          │    │ + Magic  │    │  Cols    │    │  Rank    │    │   PDF    │
│          │    │  Bytes   │    │          │    │  Filter  │    │  Excel   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘

DETAILED STAGES:

Stage 1: Upload
├── Receive file from client
├── Validate file size
├── Generate unique file ID
├── Store in temporary location
└── Create upload record in DB

Stage 2: Validate
├── Check file extension (.xlsx, .xls, .csv)
├── Verify magic bytes match extension
├── Scan for malicious content
├── Validate file structure
└── Return validation result

Stage 3: Parse
├── Open file with appropriate reader
├── Detect encoding (for CSV)
├── Extract headers
├── Map columns to expected schema
├── Convert data types
└── Handle missing values

Stage 4: Transform
├── Load workflow business rules
├── Apply filtering rules
├── Calculate aggregations
├── Rank/sort data
├── Apply top-N selection
└── Format values

Stage 5: Generate
├── Load report template
├── Populate template with data
├── Generate charts/graphs
├── Create PDF output
├── Create Excel output
├── Store in output location
└── Update report status


┌─────────────────────────────────────────────────────────────────────────────┐
│                          SUMMARY GENERATION PIPELINE                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Select  │───▶│  Load    │───▶│Aggregate │───▶│ Generate │───▶│  Format  │
│ Reports  │    │  Data    │    │ Findings │    │ Summary  │    │ Outputs  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Verify  │    │  Fetch   │    │  Merge   │    │   AI     │    │WhatsApp  │
│Completed │    │  Report  │    │  Cross-  │    │ Summary  │    │  Email   │
│  Status  │    │  Results │    │  Report  │    │ Generate │    │   PDF    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### Pipeline Characteristics

| Aspect | Approach | Rationale |
|--------|----------|-----------|
| **Execution** | Asynchronous (background jobs) | Large files need time; don't block HTTP requests |
| **Status tracking** | Polling-based | Simple implementation; WebSocket overkill for this use case |
| **Error handling** | Retry with exponential backoff | Transient failures should auto-recover |
| **Partial failure** | Continue processing valid rows | Don't fail entire report for one bad row |
| **Idempotency** | Regeneration creates new report | Preserves history; avoids data loss |

---

## 9. Automation Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AUTOMATION ENGINE PIPELINE                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              SCHEDULER                                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │  Cron Job   │    │  On-Demand  │    │   Webhook   │                     │
│  │  Trigger    │    │   Trigger   │    │   Trigger   │                     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                     │
│         └─────────────────┬┴───────────────────┘                            │
│                           ▼                                                  │
│                    ┌─────────────┐                                          │
│                    │ Job Queue   │                                          │
│                    └──────┬──────┘                                          │
└──────────────────────────┼──────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           JOB EXECUTOR                                       │
│                    ┌─────────────┐                                          │
│                    │ Job Worker  │                                          │
│                    └──────┬──────┘                                          │
│                           │                                                  │
│         ┌─────────────────┼─────────────────┐                               │
│         ▼                 ▼                 ▼                               │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                       │
│  │  RailMadad  │   │    IRCTC    │   │   Other     │                       │
│  │   Scraper   │   │   Scraper   │   │  Sources    │                       │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘                       │
│         └─────────────────┼─────────────────┘                               │
│                           ▼                                                  │
│                    ┌─────────────┐                                          │
│                    │  Playwright │                                          │
│                    │   Browser   │                                          │
│                    └──────┬──────┘                                          │
└──────────────────────────┼──────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA EXTRACTION                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │   Login     │───▶│  Navigate   │───▶│  Download   │                     │
│  │   Portal    │    │  to Report  │    │    File     │                     │
│  └─────────────┘    └─────────────┘    └─────────────┘                     │
│                                               │                             │
│                           ┌───────────────────┘                             │
│                           ▼                                                  │
│                    ┌─────────────┐                                          │
│                    │  Validate   │                                          │
│                    │  Download   │                                          │
│                    └──────┬──────┘                                          │
└──────────────────────────┼──────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         POST-PROCESSING                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │   Store     │───▶│   Notify    │───▶│  Trigger    │                     │
│  │   File      │    │   Users     │    │  Pipeline   │                     │
│  └─────────────┘    └─────────────┘    └─────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘


AUTOMATION SCHEDULE EXAMPLES:

┌──────────────────────────────────────────────────────────────────┐
│ Schedule: Daily RailMadad Complaint Download                      │
├──────────────────────────────────────────────────────────────────┤
│ Cron: 0 6 * * *  (Daily at 6:00 AM)                              │
│ Source: RailMadad Portal                                          │
│ Action: Download previous day's complaints                        │
│ Output: /uploads/railmadad/YYYY-MM-DD.xlsx                       │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Schedule: Weekly SCR Division Report                              │
├──────────────────────────────────────────────────────────────────┤
│ Cron: 0 5 * * 1  (Every Monday at 5:00 AM)                       │
│ Source: SCR Portal                                                │
│ Action: Download weekly division summary                          │
│ Output: /uploads/scr/division-YYYY-WW.xlsx                       │
└──────────────────────────────────────────────────────────────────┘
```

### Automation Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Playwright over Selenium** | Modern, faster, better debugging, native async support |
| **Headless browser** | Faster execution, lower resource usage in production |
| **Job queue** | Decouples scheduling from execution; enables retry logic |
| **Credential encryption** | Portal credentials encrypted at rest; decrypted only during execution |
| **Screenshot on failure** | Debugging aid for automation issues |

---

## 10. Security Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SECURITY ARCHITECTURE                                │
└─────────────────────────────────────────────────────────────────────────────┘

                              INTERNET
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              WAF / CDN                                       │
│  • DDoS Protection        • Rate Limiting        • Bot Detection            │
│  • Geo-blocking           • SSL Termination      • Request Filtering        │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LOAD BALANCER                                      │
│  • HTTPS Only             • Health Checks        • Session Affinity         │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
┌─────────────────────────────┐  ┌─────────────────────────────┐
│     FRONTEND (Static)       │  │     BACKEND (API)           │
│  • CSP Headers              │  │  • JWT Validation           │
│  • XSS Protection           │  │  • RBAC Enforcement         │
│  • No Secrets               │  │  • Input Validation         │
└─────────────────────────────┘  │  • Rate Limiting            │
                                 │  • Audit Logging            │
                                 └──────────────┬──────────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│    REPORT ENGINE        │  │     RULE ENGINE         │  │   AUTOMATION ENGINE     │
│  • Internal Only        │  │  • Internal Only        │  │  • Isolated Network     │
│  • No External Access   │  │  • No External Access   │  │  • Credential Vault     │
│  • File Validation      │  │  • Sandboxed Execution  │  │  • Audit All Actions    │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
                    │                           │                           │
                    └───────────────────────────┼───────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  ┌─────────────────────────┐  ┌─────────────────────────┐                  │
│  │      PostgreSQL         │  │     Object Storage      │                  │
│  │  • Encrypted at Rest    │  │  • Encrypted at Rest    │                  │
│  │  • TLS in Transit       │  │  • Private Buckets      │                  │
│  │  • Row-Level Security   │  │  • Signed URLs Only     │                  │
│  │  • Audit Logging        │  │  • Lifecycle Policies   │                  │
│  └─────────────────────────┘  └─────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐
│ Client │─────▶│ Login  │─────▶│Validate│─────▶│Generate│─────▶│  Set   │
│        │      │Request │      │Password│      │ Tokens │      │Cookies │
└────────┘      └────────┘      └────────┘      └────────┘      └────────┘
                     │               │               │               │
                     ▼               ▼               ▼               ▼
              ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
              │ Username │    │  Argon2  │    │ Access   │    │ HttpOnly │
              │ Password │    │  Verify  │    │ Refresh  │    │ SameSite │
              │          │    │          │    │  Tokens  │    │  Secure  │
              └──────────┘    └──────────┘    └──────────┘    └──────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                         REQUEST VALIDATION FLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

    Request
       │
       ▼
┌──────────────┐    No     ┌──────────────┐
│  Has Token?  │──────────▶│    401       │
└──────┬───────┘           │Unauthorized  │
       │ Yes               └──────────────┘
       ▼
┌──────────────┐    No     ┌──────────────┐
│Token Valid?  │──────────▶│    401       │
└──────┬───────┘           │ Token Expired│
       │ Yes               └──────────────┘
       ▼
┌──────────────┐    No     ┌──────────────┐
│User Active?  │──────────▶│    403       │
└──────┬───────┘           │Account Locked│
       │ Yes               └──────────────┘
       ▼
┌──────────────┐    No     ┌──────────────┐
│Has Permission│──────────▶│    403       │
└──────┬───────┘           │  Forbidden   │
       │ Yes               └──────────────┘
       ▼
┌──────────────┐    No     ┌──────────────┐
│Input Valid?  │──────────▶│    400       │
└──────┬───────┘           │ Bad Request  │
       │ Yes               └──────────────┘
       ▼
   Process Request
```

### Security Controls Matrix

| Layer | Control | Implementation |
|-------|---------|----------------|
| **Network** | TLS 1.3 | All traffic encrypted |
| **Network** | WAF Rules | OWASP Core Rule Set |
| **Auth** | Password Hashing | Argon2id |
| **Auth** | Token Storage | HttpOnly cookies |
| **Auth** | Session Duration | 30min access, 7day refresh |
| **Authz** | RBAC | Role-based permissions |
| **Input** | Validation | Pydantic schemas |
| **Upload** | File Validation | Extension + magic bytes |
| **Data** | Encryption at Rest | AES-256 |
| **Data** | Encryption in Transit | TLS 1.3 |
| **Audit** | Logging | All auth + data actions |

---

## 11. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PRODUCTION DEPLOYMENT ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────────────────┘

                              INTERNET
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │      Cloudflare        │
                    │    (WAF + CDN + DNS)   │
                    └───────────┬────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           KUBERNETES CLUSTER                                 │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         INGRESS CONTROLLER                            │  │
│  │                    (NGINX / Traefik + Cert Manager)                   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│            ┌───────────────────────┼───────────────────────┐               │
│            │                       │                       │               │
│            ▼                       ▼                       ▼               │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐       │
│  │   FRONTEND       │   │    BACKEND       │   │   ENGINES        │       │
│  │   Namespace      │   │    Namespace     │   │   Namespace      │       │
│  │                  │   │                  │   │                  │       │
│  │ ┌──────────────┐ │   │ ┌──────────────┐ │   │ ┌──────────────┐ │       │
│  │ │  Deployment  │ │   │ │  Deployment  │ │   │ │   Report     │ │       │
│  │ │  (3 pods)    │ │   │ │  (3 pods)    │ │   │ │   Engine     │ │       │
│  │ │              │ │   │ │              │ │   │ │  (2 pods)    │ │       │
│  │ │  React SPA   │ │   │ │  FastAPI     │ │   │ └──────────────┘ │       │
│  │ │  + NGINX     │ │   │ │  + Uvicorn   │ │   │                  │       │
│  │ └──────────────┘ │   │ └──────────────┘ │   │ ┌──────────────┐ │       │
│  │                  │   │                  │   │ │    Rule      │ │       │
│  │ ┌──────────────┐ │   │ ┌──────────────┐ │   │ │   Engine     │ │       │
│  │ │   Service    │ │   │ │   Service    │ │   │ │  (2 pods)    │ │       │
│  │ │ ClusterIP    │ │   │ │ ClusterIP    │ │   │ └──────────────┘ │       │
│  │ └──────────────┘ │   │ └──────────────┘ │   │                  │       │
│  │                  │   │                  │   │ ┌──────────────┐ │       │
│  │ ┌──────────────┐ │   │ ┌──────────────┐ │   │ │  Automation  │ │       │
│  │ │     HPA      │ │   │ │     HPA      │ │   │ │   Engine     │ │       │
│  │ │  (2-10 pods) │ │   │ │  (3-15 pods) │ │   │ │  (1 pod)     │ │       │
│  │ └──────────────┘ │   │ └──────────────┘ │   │ └──────────────┘ │       │
│  └──────────────────┘   └──────────────────┘   └──────────────────┘       │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                          DATA NAMESPACE                               │  │
│  │                                                                       │  │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │  │
│  │  │    PostgreSQL    │  │      Redis       │  │   MinIO / S3     │   │  │
│  │  │   (StatefulSet)  │  │   (StatefulSet)  │  │   (StatefulSet)  │   │  │
│  │  │                  │  │                  │  │                  │   │  │
│  │  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │   │  │
│  │  │  │  Primary   │  │  │  │   Master   │  │  │  │   Bucket   │  │   │  │
│  │  │  └────────────┘  │  │  └────────────┘  │  │  │  uploads   │  │   │  │
│  │  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ├────────────┤  │   │  │
│  │  │  │  Replica   │  │  │  │  Replica   │  │  │  │  reports   │  │   │  │
│  │  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │   │  │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                       MONITORING NAMESPACE                            │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐     │  │
│  │  │ Prometheus │  │  Grafana   │  │   Loki     │  │  Jaeger    │     │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                        DEVELOPMENT ENVIRONMENT                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           LOCAL DEVELOPMENT                                  │
│                                                                              │
│  Run natively: Frontend (Vite :5173), Backend (:8000), Automation (:8003),  │
│  PostgreSQL (:5432), Redis (:6379). See README.md for setup.                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Deployment Strategy

| Aspect | Strategy | Rationale |
|--------|----------|-----------|
| **Container Orchestration** | Kubernetes | Industry standard; auto-scaling; self-healing |
| **Deployments** | Rolling updates | Zero-downtime deployments |
| **Scaling** | Horizontal Pod Autoscaler | Scale based on CPU/memory metrics |
| **Database HA** | Primary-Replica | Read scaling; failover capability |
| **Secrets** | Kubernetes Secrets + Vault | Encrypted at rest; rotation support |
| **Monitoring** | Prometheus + Grafana | Standard observability stack |
| **Logging** | Loki | Log aggregation without index overhead |

---

## 12. Folder Responsibilities

### Backend Folders

| Folder | Responsibility | Changes Frequency |
|--------|----------------|-------------------|
| `api/v1/` | HTTP routing, API versioning | Low |
| `core/config.py` | Application configuration | Low |
| `core/security/` | Authentication, authorization, file validation | Low |
| `core/exceptions.py` | Domain exception definitions | Low |
| `core/logging.py` | Logging configuration | Low |
| `core/middleware.py` | Request middleware | Low |
| `domain/entities/` | Business domain objects | Medium |
| `domain/interfaces/` | Repository contracts | Low |
| `features/{name}/controller.py` | HTTP request handling | Medium |
| `features/{name}/service.py` | Business logic orchestration | High |
| `features/{name}/repository.py` | Data access implementation | Medium |
| `features/{name}/schemas.py` | Request/response DTOs | Medium |
| `features/{name}/validation.py` | Business validation rules | Medium |
| `infrastructure/database/` | ORM models, session management | Low |
| `infrastructure/seed/` | Database seeders | Low |

### Frontend Folders

| Folder | Responsibility | Changes Frequency |
|--------|----------------|-------------------|
| `api/` | HTTP client, response mapping | Medium |
| `api/schemas/` | Zod validation schemas | Medium |
| `components/ui/` | Reusable UI primitives | Low |
| `context/` | Global state providers | Medium |
| `features/{name}/components/` | Feature-specific UI | High |
| `features/{name}/hooks/` | Feature business logic | High |
| `hooks/` | Shared custom hooks | Medium |
| `layouts/` | Page layout components | Low |
| `types/` | TypeScript type definitions | Medium |
| `utils/` | Utility functions | Low |

---

## 13. Naming Conventions

### Files and Folders

| Type | Convention | Example |
|------|------------|---------|
| **Python files** | snake_case | `workflow_service.py` |
| **TypeScript files** | PascalCase for components | `WorkflowPanel.tsx` |
| **TypeScript files** | camelCase for utilities | `useWorkflowActions.ts` |
| **Test files** | `test_` prefix (Python) | `test_workflow_service.py` |
| **Test files** | `.test.ts` suffix (TS) | `workflows.test.ts` |
| **Folders** | kebab-case | `report-engine/` |

### Code Naming

| Type | Convention | Example |
|------|------------|---------|
| **Python classes** | PascalCase | `WorkflowService` |
| **Python functions** | snake_case | `get_workflow_by_id` |
| **Python constants** | SCREAMING_SNAKE | `MAX_UPLOAD_SIZE` |
| **TypeScript types** | PascalCase | `WorkflowDefinition` |
| **TypeScript functions** | camelCase | `fetchWorkflows` |
| **React components** | PascalCase | `ReportPanel` |
| **React hooks** | camelCase with `use` prefix | `useWorkflowActions` |
| **CSS classes** | kebab-case (via Tailwind) | `bg-blue-600` |

### API Naming

| Type | Convention | Example |
|------|------------|---------|
| **Endpoints** | kebab-case, plural nouns | `/api/v1/workflows` |
| **Path parameters** | camelCase | `/workflows/{workflowId}` |
| **Query parameters** | snake_case | `?page_size=10` |
| **Request/Response fields** | snake_case | `{ "workflow_id": "..." }` |

### Database Naming

| Type | Convention | Example |
|------|------------|---------|
| **Tables** | snake_case, plural | `workflow_settings` |
| **Columns** | snake_case | `created_at` |
| **Primary keys** | `id` | `id` |
| **Foreign keys** | `{table}_id` | `workflow_id` |
| **Indexes** | `ix_{table}_{column}` | `ix_users_email` |
| **Constraints** | `{table}_{type}_{column}` | `users_uq_email` |

---

## 14. API Standards

### Request Format

```json
// POST /api/v1/reports/generate
{
  "workflow_id": "division-top-25",
  "upload_id": "550e8400-e29b-41d4-a716-446655440000",
  "settings": {
    "report_date": "2026-07-04",
    "division": "hyb",
    "output_format": "pdf"
  }
}
```

### Success Response Format

```json
// 200 OK
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "workflow_id": "division-top-25",
  "status": "processing",
  "created_at": "2026-07-04T12:00:00Z"
}
```

### List Response Format

```json
// GET /api/v1/workflows
{
  "workflows": [
    { "id": "merging", "name": "Merging", ... },
    { "id": "division-top-25", "name": "Division (Top 25)", ... }
  ],
  "total": 7,
  "page": 1,
  "page_size": 20
}
```

### Error Response Format

```json
// 400 Bad Request
{
  "detail": "Invalid file extension. Allowed: .xlsx, .xls, .csv",
  "code": "VALIDATION_ERROR"
}

// 401 Unauthorized
{
  "detail": "Invalid or expired token",
  "code": "AUTHENTICATION_ERROR"
}

// 403 Forbidden
{
  "detail": "Admin access required",
  "code": "AUTHORIZATION_ERROR"
}

// 404 Not Found
{
  "detail": "Workflow with identifier 'invalid' not found",
  "code": "NOT_FOUND"
}

// 500 Internal Server Error (production)
{
  "detail": "An unexpected error occurred",
  "code": "INTERNAL_ERROR"
}
```

### HTTP Status Codes

| Code | Usage |
|------|-------|
| 200 | Successful GET, PUT, PATCH |
| 201 | Successful POST (resource created) |
| 204 | Successful DELETE (no content) |
| 400 | Validation error |
| 401 | Authentication required |
| 403 | Permission denied |
| 404 | Resource not found |
| 409 | Conflict (duplicate) |
| 422 | Unprocessable entity |
| 429 | Rate limit exceeded |
| 500 | Server error |

### Versioning Strategy

- URL-based versioning: `/api/v1/`, `/api/v2/`
- Breaking changes require new version
- Old versions supported for 12 months after deprecation notice

---

## 15. Error Handling Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ERROR HANDLING LAYERS                                │
└─────────────────────────────────────────────────────────────────────────────┘

Layer 1: Input Validation (Pydantic/Zod)
├── Catches: Malformed requests, type errors, missing fields
├── Response: 422 Unprocessable Entity
└── Action: Return validation details to client

Layer 2: Business Validation (Service Layer)
├── Catches: Business rule violations
├── Response: 400 Bad Request
└── Action: Return business error message

Layer 3: Authentication (Middleware)
├── Catches: Missing/invalid tokens
├── Response: 401 Unauthorized
└── Action: Clear auth cookies, return error

Layer 4: Authorization (Dependencies)
├── Catches: Insufficient permissions
├── Response: 403 Forbidden
└── Action: Log attempt, return error

Layer 5: Not Found (Service Layer)
├── Catches: Resource doesn't exist
├── Response: 404 Not Found
└── Action: Return friendly message

Layer 6: External Service Errors (Infrastructure)
├── Catches: Database, API failures
├── Response: 500 (sanitized) or 503
└── Action: Log full error, alert if critical

Layer 7: Unhandled Exceptions (Global Handler)
├── Catches: Everything else
├── Response: 500 Internal Server Error
└── Action: Log stack trace, return generic message


┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXCEPTION HIERARCHY                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Exception
└── AppException (base)
    ├── ValidationError (400)
    ├── AuthenticationError (401)
    ├── AuthorizationError (403)
    ├── NotFoundError (404)
    ├── ConflictError (409)
    ├── RateLimitError (429)
    ├── DatabaseError (500)
    ├── ExternalServiceError (503)
    └── ConfigurationError (500)
```

### Error Handling Rules

1. **Never expose stack traces** in production responses
2. **Always log full errors** server-side
3. **Use domain exceptions** instead of bare HTTPException
4. **Validate early** - fail fast on bad input
5. **Be specific** in development, generic in production
6. **Include error codes** for programmatic handling

---

## 16. Logging Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            LOG LEVELS                                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────┬─────────────────────────────────────────────────────────────────┐
│ LEVEL   │ USE CASE                                                        │
├─────────┼─────────────────────────────────────────────────────────────────┤
│ DEBUG   │ Detailed diagnostic info (dev only)                             │
│ INFO    │ Normal operations, service events                               │
│ WARNING │ Unexpected situations that don't affect operation               │
│ ERROR   │ Errors that need attention but don't crash                      │
│ CRITICAL│ System failures requiring immediate action                      │
└─────────┴─────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                            LOG FORMAT (JSON)                                 │
└─────────────────────────────────────────────────────────────────────────────┘

{
  "timestamp": "2026-07-04T12:00:00.000Z",
  "level": "INFO",
  "message": "Request completed",
  "module": "middleware",
  "function": "dispatch",
  "line": 42,
  "request_id": "abc123",
  "method": "POST",
  "path": "/api/v1/reports/generate",
  "status_code": 201,
  "duration_ms": 150.5,
  "user_id": "user-123"
}


┌─────────────────────────────────────────────────────────────────────────────┐
│                          WHAT TO LOG                                         │
└─────────────────────────────────────────────────────────────────────────────┘

ALWAYS LOG:
├── Request start/end with duration
├── Authentication events (login, logout, refresh)
├── Authorization failures
├── File uploads (success and rejection)
├── Report generation events
├── Database connection issues
├── External service calls
└── Unhandled exceptions

NEVER LOG:
├── Passwords (plain or hashed)
├── JWT tokens
├── API keys
├── Personal data (emails in bulk)
├── Full file contents
└── Credit card numbers


┌─────────────────────────────────────────────────────────────────────────────┐
│                          AUDIT LOGGING                                       │
└─────────────────────────────────────────────────────────────────────────────┘

Separate audit log for:
├── User authentication
├── Data modifications
├── Admin actions
├── File operations
└── Report generation

Audit log format:
{
  "timestamp": "2026-07-04T12:00:00.000Z",
  "action": "REPORT_GENERATE",
  "user_id": "user-123",
  "username": "officer.ram",
  "ip_address": "192.168.1.100",
  "resource_type": "workflow",
  "resource_id": "division-top-25",
  "success": true,
  "details": { "settings": {...} }
}
```

### Log Retention

| Log Type | Development | Production |
|----------|-------------|------------|
| Application logs | 7 days | 30 days |
| Audit logs | 30 days | 1 year |
| Error logs | 30 days | 90 days |
| Access logs | 7 days | 30 days |

---

## 17. Configuration Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CONFIGURATION HIERARCHY                                │
└─────────────────────────────────────────────────────────────────────────────┘

Priority (highest to lowest):
1. Environment variables
2. .env file (local development only)
3. Default values in code

┌─────────────────────────────────────────────────────────────────────────────┐
│                       CONFIGURATION CATEGORIES                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ SECRETS (Environment Variables Only - Never in Code)            │
├──────────────────────────────────────────────────────────────────┤
│ JWT_SECRET_KEY         - Token signing key                       │
│ CSRF_SECRET_KEY        - CSRF token key                          │
│ DATABASE_URL           - Database connection string              │
│ REDIS_URL              - Redis connection string                 │
│ AWS_ACCESS_KEY_ID      - Cloud credentials                       │
│ AWS_SECRET_ACCESS_KEY  - Cloud credentials                       │
│ PORTAL_USERNAME        - Automation credentials                  │
│ PORTAL_PASSWORD        - Automation credentials                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ ENVIRONMENT SETTINGS (Environment Variables)                     │
├──────────────────────────────────────────────────────────────────┤
│ ENVIRONMENT            - development/staging/production          │
│ DEBUG                  - Enable debug mode                       │
│ LOG_LEVEL              - Logging verbosity                       │
│ COOKIE_SECURE          - HTTPS-only cookies                      │
│ CORS_ORIGINS           - Allowed origins                         │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ BUSINESS CONFIGURATION (Database - Editable at Runtime)         │
├──────────────────────────────────────────────────────────────────┤
│ Workflow settings      - Report parameters                       │
│ Column mappings        - Data field configurations               │
│ Business rules         - Validation and ranking rules            │
│ Report templates       - Output templates                        │
│ Automation schedules   - Job scheduling                          │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ APPLICATION DEFAULTS (Code - Requires Deployment)               │
├──────────────────────────────────────────────────────────────────┤
│ MAX_UPLOAD_SIZE_MB     - File size limits (default: 50)          │
│ JWT_EXPIRE_MINUTES     - Token expiry (default: 30)              │
│ ALLOWED_EXTENSIONS     - File types (default: xlsx,xls,csv)      │
│ API_PREFIX             - API path prefix (default: /api/v1)      │
└──────────────────────────────────────────────────────────────────┘
```

### Configuration Management

| Environment | Secret Management | Config Source |
|-------------|-------------------|---------------|
| Development | `.env` file (gitignored) | Environment vars |
| Staging | Kubernetes Secrets | Environment vars |
| Production | HashiCorp Vault | Environment vars |

### Validation Rules

1. **All configs validated at startup** - Fail fast if misconfigured
2. **Type-safe settings** - Use Pydantic Settings
3. **Required secrets fail loud** - No silent defaults for secrets
4. **Document all settings** - Every config has description

---

## 18. Future Scalability Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SCALABILITY ROADMAP                                    │
└─────────────────────────────────────────────────────────────────────────────┘

PHASE 1: CURRENT (Single Region)
├── Horizontal scaling via Kubernetes HPA
├── Database read replicas
├── Redis caching
└── CDN for static assets

PHASE 2: ENHANCED (Multi-Region)
├── Database primary-replica across regions
├── Redis cluster
├── Multi-region object storage
└── Global load balancing

PHASE 3: ADVANCED
├── Event-driven architecture (Kafka/RabbitMQ)
├── CQRS for read-heavy operations
├── Microservice decomposition
└── Service mesh (Istio)


┌─────────────────────────────────────────────────────────────────────────────┐
│                       SCALING STRATEGIES BY COMPONENT                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ FRONTEND                                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ Current: CDN-hosted static files                                            │
│ Scale:   Multiple CDN edge locations                                        │
│ Future:  Edge computing for personalization                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ BACKEND API                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ Current: 3 pods with HPA (3-15)                                             │
│ Scale:   Horizontal scaling based on CPU/requests                           │
│ Future:  Auto-scaling groups, serverless for spiky loads                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ REPORT ENGINE                                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ Current: 2 pods processing synchronously                                    │
│ Scale:   Job queue with worker scaling                                      │
│ Future:  Serverless functions for burst processing                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ DATABASE                                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ Current: Primary + 1 replica                                                │
│ Scale:   Multiple read replicas, connection pooling                         │
│ Future:  Sharding by division/region, read-through cache                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ FILE STORAGE                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ Current: S3-compatible object storage                                       │
│ Scale:   Multi-region replication                                           │
│ Future:  Tiered storage (hot/cold), intelligent tiering                     │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                       FUTURE CONSIDERATIONS                                  │
└─────────────────────────────────────────────────────────────────────────────┘

1. EVENT-DRIVEN ARCHITECTURE
   ├── Decouple services via message queue
   ├── Enable async processing
   └── Support event sourcing for audit

2. CACHING LAYERS
   ├── Application-level cache (Redis)
   ├── API response cache
   └── Database query cache

3. MULTI-TENANCY (if needed)
   ├── Schema-per-tenant isolation
   ├── Row-level security
   └── Tenant-specific configurations

4. OBSERVABILITY MATURITY
   ├── Distributed tracing (Jaeger)
   ├── Metrics aggregation (Prometheus)
   └── Log correlation across services

5. DISASTER RECOVERY
   ├── Multi-region deployment
   ├── Database failover automation
   ├── RTO < 1 hour, RPO < 5 minutes
```

### Scalability Decision Framework

| Metric | Threshold | Action |
|--------|-----------|--------|
| API Latency P99 > 500ms | Sustained 5min | Scale backend pods |
| Database CPU > 80% | Sustained 5min | Add read replica |
| Report queue depth > 100 | Sustained 5min | Scale report workers |
| Storage > 80% capacity | - | Add storage, archive old data |

---

## Summary

This blueprint provides a comprehensive foundation for the Railway Report Automation Platform. Key architectural decisions:

1. **Clean Architecture** - Ensures maintainability and testability
2. **Microservices** - Enables independent scaling and deployment
3. **Security-first** - Authentication, authorization, and audit from day one
4. **Database-driven configuration** - Business rules editable without deployments
5. **Kubernetes deployment** - Production-grade orchestration

---

## Next Steps

**Awaiting confirmation to proceed to Phase 1 implementation:**

1. Set up project structure
2. Implement core authentication
3. Create base UI components
4. Establish CI/CD pipeline

Please confirm to proceed.
