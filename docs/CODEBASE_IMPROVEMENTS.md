# Codebase Improvements

This document records findings from the full-stack codebase review and tracks applied refactors.

**Last updated:** 2026-07-04

---

## 1. Executive summary

| Area | Health | Notes |
|------|--------|-------|
| Backend structure | Good | 9 feature modules; consistent layering except workflows domain layer |
| Backend security | Improved | CSRF added to templates/rules; audit user_id fixed |
| Backend duplication | Improved | Shared slug, JSON, client-IP utilities |
| Frontend structure | Fair | Dual workflow architectures; rules admin unwired |
| Frontend security | Improved | Admin routes gated; nav filtered by permissions |
| Performance | Fair | Lazy workflow config fetch; settings cache documented |
| Test coverage | Fair | Gaps in templates/rules; automation/settings/summary covered |

---

## 2. Folder structure and naming

### Backend conventions

```
backend/app/
├── api/v1/router.py          # Aggregates feature routers
├── core/                     # Config, security, shared utilities
├── domain/                   # Entities + interfaces (workflows only today)
├── features/<name>/          # controller, service, repository, schemas, dependencies
└── infrastructure/           # DB models, seed, session
```

**Router prefix convention:** Admin CRUD may use `/admin/<resource>` (templates) or `/<resource>` (rules, summary). Documented as historical; unify in a future major version if desired.

**Repository convention:** Use `self._session` for the async SQLAlchemy session attribute.

### Frontend conventions

```
src/
├── api/                      # *Api object clients + client.ts
├── features/<domain>/        # Pages, hooks, components
├── components/ui/            # Shared primitives
└── components/admin/         # Shared admin list components
```

**Workflow UI:** Two paths coexist — see Section 4.

---

## 3. Duplicate code inventory

| Duplication | Locations | Resolution |
|-------------|-----------|------------|
| Slug generation | templates/service, summary/service | `app/core/slug.py` |
| JSON serialize/deserialize | settings, automation repos | `app/core/json_utils.py` |
| Client IP extraction | auth/dependencies, rate_limit | `app/core/request_utils.py` |
| Admin list pages | TemplateListPage, PromptListPage | `components/admin/*` |
| Query string building | rules, summary, settings API | `buildQueryString()` in client.ts |
| Settings renderers | SettingsCard, SettingsRenderer, SettingField | Documented; unify in future migration |

---

## 4. Unused and orphaned files

### Removed

| Path | Reason |
|------|--------|
| `backend/app/application/__init__.py` | Never imported |
| `backend/app/features/workflows/tests/__init__.py` | Empty misplaced package |

### Orphaned (kept, documented)

| Path | Status |
|------|--------|
| `src/features/workflows/WorkflowPage.tsx` | Not routed; legacy API-driven workflow |
| `src/features/admin/rules/*` | Built but unwired; missing subcomponents |
| `src/components/ui/ErrorState.tsx` | No imports; kept for future use |
| `src/components/ui/LoadingOverlay.tsx` | No imports |
| `src/components/ui/ProgressIndicator.tsx` | No imports |
| `src/api/schemas/workflow.ts` | Zod schemas unused |

### Dead code removed from modules

- `validate_accepted_file_extensions()` in `workflows/validation.py`
- `FileValidator.generate_safe_path()` in `file_validator.py`
- Duplicate upload size check in `uploads/controller.py`

---

## 5. Security findings

| Finding | Severity | Status |
|---------|----------|--------|
| CSRF missing on templates/rules mutations | High | **Fixed** |
| Rules audit `user_id` always None | Medium | **Fixed** |
| Automation callback token timing attack | Low | **Fixed** (`compare_digest`) |
| Client permissions not enforced in UI | Medium | **Fixed** (RequireAdmin + nav filter) |
| Encryption key falls back to JWT secret | Low | Documented in `.env.example` |
| Rate limit bypass without Redis | Medium | Documented; deferred |
| Upload magic bytes not validated | Medium | Documented; deferred |
| Default dev secrets in config | Medium | Documented; use env in production |

---

## 6. Performance

| Issue | Impact | Status |
|-------|--------|--------|
| Global `/workflows` fetch on every load | Medium | **Fixed** — lazy WorkflowConfigProvider |
| React Query configured but unused | Low | Documented; optional migration |
| Settings cache `KEYS` scan | Low at scale | Documented; use SCAN later |
| Workflows list eager-loads all relations | Medium payload | Documented; intentional for `/workflows` API |
| Automation 3x COUNT queries | Low | Documented |

---

## 7. Maintainability

- **Dual config systems:** Legacy `workflow_settings` + `report_config_templates` / `ConfigurableRuleModel` — no merge in this pass.
- **Audit layer:** Only auth + uploads emit audit events; settings/rules/templates mutations documented as gap.
- **Test gaps:** templates and rules now have controller smoke tests; health still untested.

---

## 8. Changelog of applied refactors

### 2026-07-04 — Codebase review implementation

**Documentation**
- Created this file
- Added pointer in README.md

**Backend — shared utilities**
- Added `app/core/slug.py`, `json_utils.py`, `request_utils.py`
- Templates and summary services use shared slug helper
- Settings and automation repositories use shared JSON helpers
- Auth and rate_limit use shared client IP helper
- Template repository: `_session` naming, eager-load constant
- Added `uploads/dependencies.py`

**Backend — dead code**
- Removed unused modules and validation helpers listed above

**Backend — security**
- CSRF on all templates and rules mutating endpoints
- Rules controller uses `User` entity and `user.id`
- Automation service token compared with `secrets.compare_digest`

**Frontend — security**
- Admin routes wrapped in `RequireAdmin`
- AppShell admin nav filtered by `usePermissions`

**Frontend — deduplication**
- `buildQueryString()` in `api/client.ts`
- `workflowsApi` alias alongside legacy `fetchWorkflows`
- Lazy `WorkflowConfigProvider` on workflow layout only
- Shared `AdminListToolbar`, `ConfirmDialog`, `DuplicateNameDialog`

**Tests**
- CSRF tests for templates/rules mutations (400 without token)
- Rules `created_by` / `updated_by` population test on create
- Full pytest suite: 87 passed
- Frontend typecheck passes (unwired `admin/rules` excluded from compilation)

**Other fixes**
- Removed unused `report_engine_url` / `rule_engine_url` from config
- Fixed `duplicate_rule` FastAPI parameter ordering syntax error
- Fixed orphaned `SummaryPanel` missing `handleDownloadAll` destructure

---

## 9. Out of scope (future work)

- Merge legacy workflows DB with report config engine
- Delete orphaned WorkflowPage stack
- Wire admin/rules routes and complete editor components
- Connect WorkflowPageLayout to real report APIs
- Full React Query migration for admin lists
- Production Redis requirement for rate limiting
