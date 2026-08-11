from fastapi import APIRouter

from app.features.activity.controller import router as activity_router
from app.features.auth.controller import router as auth_router
from app.features.automation.controller import router as automation_router
from app.features.dashboard.controller import router as dashboard_router
from app.features.health.controller import router as health_router
from app.features.rules.controller import router as rules_router
from app.features.settings.controller import router as settings_router
from app.features.summary.controller import router as summary_router
from app.features.daily_summary.controller import router as daily_summary_router
from app.features.system.controller import router as system_router
from app.features.templates.controller import router as templates_router
from app.features.datasets.controller import router as datasets_router
from app.features.uploads.controller import router as uploads_router
from app.features.workflows.controller import router as workflows_router
from app.features.reports.controller import router as manual_reports_router
from app.api.automation import router as in_process_automation_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(activity_router)
api_router.include_router(dashboard_router)
api_router.include_router(workflows_router)
api_router.include_router(uploads_router)
api_router.include_router(datasets_router)
api_router.include_router(templates_router)
api_router.include_router(rules_router)
api_router.include_router(summary_router)
api_router.include_router(daily_summary_router)
api_router.include_router(settings_router)
api_router.include_router(system_router)
api_router.include_router(automation_router)
api_router.include_router(in_process_automation_router)
api_router.include_router(manual_reports_router)
